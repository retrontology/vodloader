import argparse
import os
import logging, logging.handlers
import asyncio
import signal
import sys
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

    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Register signal handlers for both SIGINT (Ctrl+C) and SIGTERM (systemd)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Store tasks for cleanup
    api_task = None
    transcode_task = None
    chatbot_task = None
    
    try:
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
        hypercorn_config.graceful_timeout = 5  # Allow 5 seconds for graceful shutdown
        api = create_api()

        # Create all async tasks
        api_task = asyncio.create_task(serve(api, hypercorn_config))
        transcode_task = asyncio.create_task(transcode_listener())

        # Queue existing videos for transcoding
        await queue_trancodes()
        
        logger.info("All services started successfully. Press Ctrl+C to stop.")
        
        # Wait for shutdown signal or task completion
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(shutdown_event.wait()),
                api_task,
                transcode_task,
                chatbot_task
            ],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Check if any tasks completed with exceptions
        for task in done:
            if not task.cancelled() and task.exception():
                logger.error(f"Task failed with exception: {task.exception()}")
                
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
    finally:
        await cleanup_services(logger, api_task, transcode_task, chatbot_task)


async def cleanup_services(logger, api_task, transcode_task, chatbot_task):
    """Cleanup all services gracefully"""
    logger.info('Shutting down services...')
    
    # Cancel tasks gracefully with timeout
    tasks_to_cancel = [task for task in [api_task, transcode_task, chatbot_task] if task and not task.done()]
    
    if tasks_to_cancel:
        logger.info(f"Cancelling {len(tasks_to_cancel)} running tasks...")
        for task in tasks_to_cancel:
            task.cancel()
        
        # Wait for tasks to complete cancellation with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("Some tasks did not complete cancellation within timeout")
    
    # Cleanup chat bot
    try:
        from vodloader.chat import bot
        bot.die()
        bot.disconnect()
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error cleaning up chat bot: {e}")
    
    # Cleanup webhooks and twitch connection with timeout
    cleanup_tasks = []
    
    try:
        cleanup_tasks.append(webhook.unsubscribe_all())
    except Exception as e:
        logger.error(f"Error creating webhook unsubscribe task: {e}")
    
    try:
        cleanup_tasks.append(webhook.stop())
    except Exception as e:
        logger.error(f"Error creating webhook stop task: {e}")
    
    try:
        cleanup_tasks.append(twitch.close())
    except Exception as e:
        logger.error(f"Error creating twitch close task: {e}")
    
    if cleanup_tasks:
        try:
            cleanup_results = await asyncio.wait_for(
                asyncio.gather(*cleanup_tasks, return_exceptions=True),
                timeout=5.0
            )
            
            # Log any cleanup errors
            cleanup_names = ['webhook unsubscribe', 'webhook stop', 'twitch close']
            for i, result in enumerate(cleanup_results):
                if isinstance(result, Exception):
                    logger.error(f"Error during {cleanup_names[i]}: {result}")
        except asyncio.TimeoutError:
            logger.warning("Cleanup operations timed out")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    logger.info("Shutdown complete")



if __name__ == '__main__':
    asyncio.run(main())
