"""
Chat video generation for Twitch VODs.

This module provides basic functionality to overlay chat messages on video streams.
The complex implementation has been removed - use Spec to build a better solution.
"""

import asyncio
import logging
from typing import Optional
from vodloader.models import VideoFile

logger = logging.getLogger('vodloader.chat_video')

# Import from the simplified structure if available
try:
    from .chat import (
        ChatVideoGenerator,
        generate_chat_video as _generate_chat_video
    )
    _has_chat_implementation = True
except ImportError:
    _has_chat_implementation = False
    logger.warning("Chat implementation not available, using stub")


async def generate_chat_video(video: VideoFile, cancellation_event: Optional[asyncio.Event] = None):
    """
    Generate chat video with cancellation support.
    
    Args:
        video: The video file to process
        cancellation_event: Event to signal cancellation
        
    Returns:
        Path to generated video or None if no chat messages found
        
    Raises:
        asyncio.CancelledError: If operation is cancelled
    """
    # Check for cancellation before starting
    if cancellation_event and cancellation_event.is_set():
        raise asyncio.CancelledError("Chat video generation cancelled before starting")
    
    if _has_chat_implementation:
        try:
            # Call the actual implementation with cancellation support
            return await _generate_chat_video(video, cancellation_event)
        except asyncio.CancelledError:
            logger.info(f"Chat video generation cancelled for video {video.id}")
            raise
        except Exception as e:
            logger.error(f"Error generating chat video for {video.id}: {e}")
            return None
    else:
        # Stub implementation - just return None to indicate no chat video generated
        logger.info(f"Chat video generation not implemented, skipping for video {video.id}")
        return None


class ChatVideoGenerator:
    """Stub chat video generator class"""
    
    def __init__(self):
        logger.warning("ChatVideoGenerator stub initialized - no actual functionality")
    
    async def generate(self, video: VideoFile, cancellation_event: Optional[asyncio.Event] = None):
        """Stub generate method"""
        return await generate_chat_video(video, cancellation_event)


# Re-export for backward compatibility
__all__ = [
    'ChatVideoGenerator',
    'generate_chat_video'
]