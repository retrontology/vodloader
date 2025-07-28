"""
Chat video generation for Twitch VODs.

This module provides functionality to overlay chat messages on video streams
with proper timing and formatting.

This is a compatibility layer that imports from the new modular structure.
"""

# Import all classes and functions from the new modular structure
from .chat import (
    ChatVideoConfig,
    ChatVideoGenerator,
    ChatRenderer,
    ChatArea,
    FontManager,
    VideoProcessor,
    generate_chat_video
)

# Re-export everything for backward compatibility
__all__ = [
    'ChatVideoConfig',
    'ChatVideoGenerator',
    'ChatRenderer', 
    'ChatArea',
    'FontManager',
    'VideoProcessor',
    'generate_chat_video'
]