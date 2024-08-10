import argparse
import os
import logging, logging.handlers
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from .config import Config
from .database import *
from .oauth import DBUserAuthenticationStorageHelper
from .models import *
import asyncio
from pathlib import Path
from .vodloader import VODLoader

DEFAULT_CONFIG = default=os.path.join(
    os.path.dirname(__file__),
    'config.yml'
)
TARGET_SCOPE = []
DATABASE = None

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
    logger.handlers.append(file_handler)
    logger.handlers.append(stream_handler)
    return logging.getLogger('vodloader')

async def main():

    # Initialize args, config, and logger
    args = parse_args()
    logger = setup_logger(args.debug)
    logger.info(f'Loading configuration from {args.config}')
    config = Config(args.config)
    download_dir = Path()
    if not download_dir.exists():
        download_dir.mkdir()

    #Initialize database
    mysql = False
    if mysql:
        database = await MySQLDatabase.create(
            host=config['database']['host'],
            port=config['database']['port'],
            user=config['database']['user'],
            password=config['database']['password'],
            schema=config['database']['schema'],
        )
    else:
        database = await SQLLiteDatabase.create('test.sql')
    await database.set_twitch_client(
        config['twitch']['client_id'],
        config['twitch']['client_secret']
    )

    # Log into Twitch
    logger.info(f'Logging into Twitch')
    twitch = await Twitch(
        config['twitch']['client_id'],
        config['twitch']['client_secret'],
    )

    # Authenticate Twitch User
    auth = DBUserAuthenticationStorageHelper(
        twitch=twitch,
        scopes=TARGET_SCOPE,
        database=database,
    )
    await auth.bind()

    # Initialize Webhook
    logger.info(f'Initializing EventSub Webhook')
    eventsub = EventSubWebhook(f"https://{config['host']}", 8000, twitch)
    await eventsub.unsubscribe_all()
    eventsub.start()

    # Initialize VODLoader
    vodloader = VODLoader(
        database=database,
        twitch=twitch,
        eventsub=eventsub,
        download_dir=config['download']['directory']
    )
    await vodloader.start()

    # Main loop & cleanup
    try:
        input('press Enter to shut down...')
    finally:
        await eventsub.unsubscribe_all()
        await eventsub.stop()
        await twitch.close()


if __name__ == '__main__':
    asyncio.run(main())
