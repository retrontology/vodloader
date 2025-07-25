"""
Post-processing functionality for Twitch VODs.

This module provides a compatibility layer for the post-processing functionality
that has been moved to the post/ subdirectory.
"""

# Import everything from the post module for backward compatibility
from .post import *

# Re-export the transcode_queue for direct access
from .post.transcoding import transcode_queue