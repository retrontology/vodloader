"""
Chat video generation package.

This package provides functionality to overlay chat messages on video streams
with proper timing and formatting.
"""

from .config import ChatVideoConfig
from .generator import ChatVideoGenerator
from .renderer import ChatRenderer
from .area import ChatArea
from .font_manager import FontManager
from .video_processor import VideoProcessor

# Convenience function for backward compatibility
from .generator import generate_chat_video

__all__ = [
    'ChatVideoConfig',
    'ChatVideoGenerator', 
    'ChatRenderer',
    'ChatArea',
    'FontManager',
    'VideoProcessor',
    'generate_chat_video'
]