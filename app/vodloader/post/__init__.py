"""
Post-processing module for Twitch VODs.

This module contains all post-processing functionality including:
- Video transcoding
- Ad detection and removal
- Chat overlay generation
- Video processing utilities
"""

from .transcoding import transcode, remove_original, transcode_listener, queue_trancodes
from .chat_video import generate_chat_video, ChatVideoGenerator, ChatVideoConfig
from .ad_detection import AdDetector, VideoSegment, StreamProperties

__all__ = [
    # Transcoding
    'transcode',
    'remove_original', 
    'transcode_listener',
    'queue_trancodes',
    
    # Chat video generation
    'generate_chat_video',
    'ChatVideoGenerator',
    'ChatVideoConfig',
    
    # Ad detection
    'AdDetector',
    'VideoSegment', 
    'StreamProperties',
]