"""
Chat video generation for Twitch VODs.

This module provides basic functionality to overlay chat messages on video streams.
The complex implementation has been removed - use Spec to build a better solution.
"""

# Import from the simplified structure
from .chat import (
    ChatVideoGenerator,
    generate_chat_video
)

# Re-export for backward compatibility
__all__ = [
    'ChatVideoGenerator',
    'generate_chat_video'
]