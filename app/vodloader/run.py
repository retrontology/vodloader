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
from vodloader.post import transcode_listener, transcode_queue, queue_trancodes
from vodloader import config


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


async def start_chat_bot():
    """Start chat bot as an async task instead of thread"""
    try:
        # Import here to avoid circular imports
        from vodloader.chat import bot
        await bot.start_async()
    except ImportError:
        logger.warning("Chat bot module not found, skipping chat functionality")
        return None
    except Exception as e:
        logger.error(f"Failed to start chat bot: {e}")
        return None


async def main():
    # Initialize args
    args = parse_args()
    logger = setup_logger(args.debug)

    # Initialize DB
    await initialize_models()

    # Initialize Twitch Connections
    await twitch.authenticate_app([])
    webhook.start()
    await webhook.unsubscribe_all()

    # Start chat bot as async task
    chatbot_task = asyncio.create_task(start_chat_bot())
    
    # Give chat bot time to connect
    await asyncio.sleep(2)

    # Subscribe to all active channel webhooks
    channels = await TwitchChannel.get_many(active=True)
    tasks = []
    
    for channel in channels:
        # Try to join channel if bot is available
        try:
            from vodloader.chat import bot
            bot.join_channel(channel)
        except ImportError:
            pass
        
        # Subscribe to webhooks
        tasks.append(subscribe(channel))
    
    # Subscribe to all channels concurrently
    if tasks:
        await asyncio.gather(*tasks)

    # Setup API
    hypercorn_config = HypercornConfig()
    hypercorn_config.bind = [f"{config.API_HOST}:{config.API_PORT}"]
    api = create_api()

    # Create all async tasks
    api_task = asyncio.create_task(serve(api, hypercorn_config))
    transcode_task = asyncio.create_task(transcode_listener())

    # Queue existing videos for transcoding
    await queue_trancodes()
    
    # Run all tasks concurrently with proper error handling
    try:
        results = await asyncio.gather(
            api_task,
            transcode_task,
            chatbot_task,
            return_exceptions=True
        )
        
        # Log any exceptions that occurred
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_names = ['API', 'Transcode', 'Chat Bot']
                logger.error(f"{task_names[i]} task failed: {result}")
                
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        # Cleanup
        logger.info('Shutting down services...')
        
        # Cancel tasks gracefully
        tasks_to_cancel = [api_task, transcode_task, chatbot_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        # Cleanup chat bot
        try:
            from vodloader.chat import bot
            bot.die()
            bot.disconnect()
        except ImportError:
            pass
        
        # Cleanup webhooks and twitch connection
        cleanup_tasks = [
            webhook.unsubscribe_all(),
            webhook.stop(),
            twitch.close()
        ]
        
        cleanup_results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Log any cleanup errors
        for i, result in enumerate(cleanup_results):
            if isinstance(result, Exception):
                cleanup_names = ['webhook unsubscribe', 'webhook stop', 'twitch close']
                logger.error(f"Error during {cleanup_names[i]}: {result}")
        
        logger.info("Shutdown complete")



if __name__ == '__main__':
    asyncio.run(main())
