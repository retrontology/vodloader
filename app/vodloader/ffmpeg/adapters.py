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


async def get_video_info(video_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Adapter for existing get_video_info function.
    
    This maintains the old dictionary interface while using the new probe_video internally.
    Helps with gradual migration.
    """
    info = await probe_video(video_path)
    
    # Convert VideoInfo back to dictionary format for backward compatibility
    return {
        'width': info.width,
        'height': info.height,
        'frame_rate': info.frame_rate,
        'duration': info.duration,
        'codec': info.codec,
        'bitrate': info.bitrate,
        'has_audio': info.has_audio
    }


def ffmpeg_probe_adapter(video_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Synchronous adapter for ffmpeg.probe() calls.
    
    This allows existing synchronous code to work while internally using
    the async probe_video function.
    """
    try:
        # Run the async function in a new event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't use run()
                # This is a limitation - sync code should be migrated to async
                raise RuntimeError(
                    "Cannot call synchronous probe from async context. "
                    "Please use 'await probe_video()' instead."
                )
        except RuntimeError:
            # No event loop running, create one
            loop = None
        
        if loop is None:
            return asyncio.run(_async_probe_wrapper(video_path))
        else:
            # We're in an async context but the caller expects sync
            logger.warning(
                f"Synchronous probe called from async context for {video_path}. "
                "Consider migrating to async probe_video()."
            )
            raise RuntimeError("Use async probe_video() in async contexts")
            
    except Exception as e:
        logger.error(f"Probe adapter failed for {video_path}: {e}")
        raise


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
    def probe(video_path: Union[str, Path]) -> Dict[str, Any]:
        """Legacy probe interface."""
        return ffmpeg_probe_adapter(video_path)
    
    @staticmethod
    async def async_probe(video_path: Union[str, Path]) -> Dict[str, Any]:
        """Async version of legacy probe."""
        return await _async_probe_wrapper(video_path)
    
    @staticmethod
    async def simple_transcode(
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        vcodec: str = 'copy',
        acodec: str = 'copy'
    ) -> Path:
        """Legacy transcode interface."""
        return await transcode_video(
            input_path=input_path,
            output_path=output_path,
            video_codec=vcodec,
            audio_codec=acodec
        )


# Convenience imports for backward compatibility
legacy_ffmpeg = LegacyFFmpegInterface()