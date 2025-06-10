import argparse
import os
import logging, logging.handlers
import asyncio
from hypercorn.config import Config as HypercornConfig
from hypercorn.asyncio import serve
from vodloader.models import TwitchChannel, VideoFile, initialize_models
from vodloader.api import create_api
from vodloader.twitch import twitch, webhook
from vodloader.vodloader import subscribe
from vodloader.chat import bot
from vodloader.post import transcode_listener, transcode_queue
from vodloader import config
from threading import Thread


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

    # Initialize args
    args = parse_args()
    logger = setup_logger(args.debug)
    loop = asyncio.get_event_loop()

    # Initialize DB
    await initialize_models()

    # Intialize Twitch Connections
    await twitch.authenticate_app([])
    webhook.start()
    await webhook.unsubscribe_all()

    # Start chat bot
    chatbot_task = Thread(target=bot.start, daemon=True)
    chatbot_task.start()
    while not bot.connection.connected:
        await asyncio.sleep(1)

    # Subscribe to all active channel webhooks
    channels = await TwitchChannel.get_many(active=True)
    for channel in channels:
        bot.join_channel(channel)
        await subscribe(channel)

    # Run API
    hypercorn_config = HypercornConfig()
    hypercorn_config.bind = [f"{config.API_HOST}:{config.API_PORT}"]
    api = create_api()

    # Run tasks
    api_task = loop.create_task(serve(api, hypercorn_config))
    transcode_task = loop.create_task(transcode_listener())

    # Look for videos that need transcoding
    videos = await VideoFile.get_nontranscoded()
    for video in videos:
        await transcode_queue.put(video)
    
    # Await everything
    await api_task
    await transcode_task

    # Cleanup
    logger.info('Shutting down the chatbot...')
    bot.die()
    bot.disconnect()
    logger.info('Shutting down the webhooks...')
    await asyncio.gather(webhook.unsubscribe_all(), webhook.stop(), twitch.close())



if __name__ == '__main__':
    asyncio.run(main())
