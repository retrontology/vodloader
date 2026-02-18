"""
Adapter functions to help migrate existing code to the unified ffmpeg interface.

These provide backward compatibility while encouraging migration to the new interface.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Union

from .core import probe_video, VideoInfo, transcode_video

logger = logging.getLogger('vodloader.ffmpeg.adapters')




async def _async_probe_wrapper(video_path: Union[str, Path]) -> Dict[str, Any]:
    """Wrapper to convert VideoInfo to old format."""
    info = await probe_video(video_path)
    
    # Return in the old ffmpeg.probe() format
    return {
        'streams': [
            {
                'codec_type': 'video',
                'width': info.width,
                'height': info.height,
                'r_frame_rate': f"{info.frame_rate:.0f}/1",
                'duration': str(info.duration),
                'codec_name': info.codec,
                'bit_rate': str(info.bitrate) if info.bitrate else None
            }
        ] + ([{
            'codec_type': 'audio'
        }] if info.has_audio else [])
    }


class LegacyFFmpegInterface:
    """
    Legacy interface adapter for gradual migration.
    
    This class provides the old interface while using new implementations internally.
    """
    

    @staticmethod
    async def async_probe(video_path: Union[str, Path]) -> Dict[str, Any]:
        """Async version of legacy probe."""
        return await _async_probe_wrapper(video_path)
    



# Convenience imports for backward compatibility
legacy_ffmpeg = LegacyFFmpegInterface()