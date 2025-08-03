"""
Chat video generation module.

Provides components for generating chat overlay videos from Twitch chat data
using browser automation and video processing.
"""

from .generator import ChatVideoGenerator, generate_chat_video, ChatOverlayError, ChatDataError
from .browser_manager import BrowserManager, BrowserManagerError, BrowserTimeoutError, BrowserResourceError, browser_context
from .chat_renderer import ChatRenderer, ChatRendererError, VideoMetadataError
from .video_compositor import VideoCompositionError, FrameRateMismatchError

__all__ = [
    'ChatVideoGenerator',
    'generate_chat_video',
    'ChatOverlayError',
    'ChatDataError',
    'BrowserManager',
    'BrowserManagerError', 
    'BrowserTimeoutError',
    'BrowserResourceError',
    'browser_context',
    'ChatRenderer',
    'ChatRendererError',
    'VideoMetadataError',
    'VideoCompositionError',
    'FrameRateMismatchError'
]