import argparse
import os
import logging, logging.handlers
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from .models import *
from .util import get_download_dir
import asyncio
import concurrent.futures
from .vodloader import VODLoader
from dotenv import load_dotenv
from hypercorn.config import Config
from hypercorn.asyncio import serve
from .api import create_api


def parse_args():
    parser = argparse.ArgumentParser(
        prog='vodloader',
        description='Automate uploading Twitch streams to YouTube'
    )
    parser.add_argument(
        '-d', '--debug',
        default=logging.INFO,
        const=logging.DEBUG,
        action='store_const'
    )
    return parser.parse_args()

def setup_logger(level=logging.INFO, path='logs'):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        os.mkdir(path)
    logger = logging.getLogger()
    logger.setLevel(level)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(path, 'vodloader.log'),
        when='midnight'
    )
    stream_handler = logging.StreamHandler()
    format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(format)
    stream_handler.setFormatter(format)
    file_handler.setLevel(level)
    stream_handler.setLevel(level)
    logger.handlers.append(file_handler)
    logger.handlers.append(stream_handler)
    return logging.getLogger('vodloader')

async def main():

    # Initialize env, args, and logger
    load_dotenv()
    args = parse_args()
    logger = setup_logger(args.debug)

    # Initialize download dir
    download_dir = get_download_dir()
    if not download_dir.exists():
        download_dir.mkdir()
    
    #Initialize database
    await initialize_models()

    # Log into Twitch
    logger.info(f'Logging into Twitch')
    twitch = await Twitch(
        os.environ['TWITCH_CLIENT_ID'],
        os.environ['TWITCH_CLIENT_SECRET'],
    )

    # Initialize Webhook
    logger.info(f'Initializing EventSub Webhook')
    eventsub = EventSubWebhook(f"https://{os.environ['WEBHOOK_HOST']}", 8000, twitch)
    await eventsub.unsubscribe_all()
    eventsub.start()
    loop = asyncio.get_event_loop()

    # Initialize VODLoader
    vodloader = VODLoader(
        twitch=twitch,
        eventsub=eventsub,
        download_dir=download_dir
    )
    vodloader_task = loop.create_task(vodloader.start())

    # Run API
    config = Config()
    config.bind = ["0.0.0.0:8001"]
    config.__setattr__('vodloader', vodloader)
    api = create_api(vodloader)
    api_task = loop.create_task(serve(api, config))
    
    # Await everything
    await api_task
    await vodloader_task

    # Cleanup
    await vodloader.stop()
    await eventsub.unsubscribe_all()
    await eventsub.stop()
    await twitch.close()


if __name__ == '__main__':
    asyncio.run(main())
