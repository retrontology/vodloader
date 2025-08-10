"""
Unified FFmpeg interface for vodloader.

This module provides a seamless layer over both ffmpeg-python and direct subprocess
approaches, choosing the optimal method based on the operation type.
"""

from .core import (
    probe_video,
    transcode_video,
    StreamingComposer,
    FFmpegError,
    VideoInfo
)

from .utils import (
    calculate_overlay_position,
    parse_frame_rate,
    format_duration
)

__all__ = [
    'probe_video',
    'transcode_video', 
    'StreamingComposer',
    'FFmpegError',
    'VideoInfo',
    'calculate_overlay_position',
    'parse_frame_rate',
    'format_duration'
]