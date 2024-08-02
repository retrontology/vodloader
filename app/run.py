import argparse
import os
import logging, logging.handlers
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.eventsub.webhook import EventSubWebhook
from channels import Channel
from config import Config
import asyncio

DEFAULT_CONFIG = default=os.path.join(
    os.path.dirname(__file__),
    'config.yml'
)

def parse_args():
    parser = argparse.ArgumentParser(
        prog='vodloader',
        description='Automate uploading Twitch streams to YouTube'
    )
    parser.add_argument(
        '-c', '--config',
        default=DEFAULT_CONFIG,
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
    return logger

async def main():

    # Initialize args, config, and logger
    args = parse_args()
    logger = setup_logger(args.debug)
    logger.info(f'Loading configuration from {args.config}')
    config = Config(args.config)

    # Log into Twitch
    logger.info(f'Logging into Twitch')
    twitch = await Twitch(
        config['twitch']['client_id'],
        config['twitch']['client_secret'],
    )

    # Initialize Webhook
    auth = UserAuthenticator(twitch, [])
    await auth.authenticate()
    logger.info(f'Initializing EventSub Webhook')
    eventsub = EventSubWebhook(f"https://{config['host']}", 8000, twitch)
    await eventsub.unsubscribe_all()
    eventsub.start()

    channels = []
    for channel_name in config['twitch']['channels']:
        channel = config['twitch']['channels'][channel_name]
        channels.append(
            await Channel.create(
                channel_name,
                twitch,
                eventsub,
                channel['backlog'],
                channel['chapters'],
                channel['quality'],
                channel['timezone'],
            )
        )

    try:
        input('press Enter to shut down...')
    finally:
        await eventsub.stop()
        await twitch.close()


if __name__ == '__main__':
    asyncio.run(main())
