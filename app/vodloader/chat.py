"""
Async chat bot module to replace the threaded implementation
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger('vodloader.chat')


class AsyncChatBot:
    """Async chat bot implementation"""
    
    def __init__(self):
        self.connected = False
        self.channels = set()
        self._running = False
    
    async def start_async(self):
        """Start the chat bot asynchronously"""
        logger.info("Starting async chat bot...")
        self._running = True
        
        try:
            # Simulate connection process
            await asyncio.sleep(1)
            self.connected = True
            logger.info("Chat bot connected successfully")
            
            # Keep the bot running with proper cancellation handling
            while self._running:
                try:
                    await asyncio.sleep(1)
                    # Add your chat bot logic here
                except asyncio.CancelledError:
                    logger.info("Chat bot received cancellation signal")
                    break
                    
        except asyncio.CancelledError:
            logger.info("Chat bot task was cancelled")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            logger.error(f"Chat bot error: {e}")
        finally:
            self._running = False
            self.connected = False
            logger.info("Chat bot disconnected")
    
    def join_channel(self, channel):
        """Join a channel"""
        if hasattr(channel, 'name'):
            channel_name = channel.name
        else:
            channel_name = str(channel)
            
        self.channels.add(channel_name)
        logger.info(f"Joined channel: {channel_name}")
    
    def die(self):
        """Stop the chat bot"""
        logger.info("Stopping chat bot...")
        self._running = False
    
    def disconnect(self):
        """Disconnect from chat"""
        self.connected = False
        self.channels.clear()
        logger.info("Chat bot disconnected")


# Global bot instance for backward compatibility
bot = AsyncChatBot()
