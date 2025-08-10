"""
Video compositor for chat overlay composition.

This module handles the composition of original stream videos with chat overlay videos
using the unified FFmpeg interface. It supports configurable positioning, frame rate 
synchronization, and quality preservation with streaming composition.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, AsyncGenerator

from vodloader.models.ChannelConfig import ChannelConfig
from vodloader.ffmpeg import probe_video, StreamingComposer, calculate_overlay_position, VideoInfo
from playwright.async_api import Page

logger = logging.getLogger('vodloader.post.chat.video_compositor')


class VideoCompositionError(Exception):
    """Raised when video composition fails."""
    pass


class FrameRateMismatchError(VideoCompositionError):
    """Raised when video frame rates don't match."""
    pass


async def get_video_info(video_path: Path) -> VideoInfo:
    """
    Get video metadata including frame rate, dimensions, and duration.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        VideoInfo object containing metadata
        
    Raises:
        VideoCompositionError: If video info cannot be retrieved
    """
    try:
        return await probe_video(video_path)
    except Exception as e:
        raise VideoCompositionError(f"Failed to get video info for {video_path}: {e}")


# Note: calculate_overlay_position is now imported from vodloader.ffmpeg


async def composite_videos(
    original_path: Path,
    page: Page,
    output_path: Path,
    config: ChannelConfig,
    frame_generator: AsyncGenerator[bytes, None],
    total_frames: int
) -> None:
    """
    Composite original video with streaming chat overlay frames directly.
    
    This method uses the unified FFmpeg interface for streaming composition.
    
    Args:
        original_path: Path to the original video file
        page: Playwright page instance for generating overlay frames
        output_path: Path where the composite video will be saved
        config: Channel configuration containing overlay settings
        frame_generator: Async generator yielding PNG frame bytes
        total_frames: Total number of frames to process
        
    Raises:
        VideoCompositionError: If composition fails
    """
    logger.info(f"Starting streaming video composition: {original_path} -> {output_path}")
    
    try:
        # Get original video information using unified interface
        logger.debug("Analyzing original video file")
        original_info = await get_video_info(original_path)
        
        logger.info(
            f"Original video: {original_info.resolution_string} "
            f"@ {original_info.frame_rate:.2f}fps, {original_info.duration:.1f}s, "
            f"codec: {original_info.codec}"
        )
        
        # Calculate overlay dimensions and position
        overlay_width, overlay_height = _calculate_overlay_dimensions_from_page(page, config, original_info)
        position = config.get_chat_position()
        padding = config.get_chat_padding()
        
        overlay_x, overlay_y = calculate_overlay_position(
            original_info.width,
            original_info.height,
            overlay_width,
            overlay_height,
            position,
            padding
        )
        
        logger.info(
            f"Streaming overlay: {overlay_width}x{overlay_height} at ({overlay_x}, {overlay_y}) "
            f"with position='{position}' and padding={padding}px"
        )
        
        # Use unified streaming composer
        composer = StreamingComposer()
        
        await composer.compose_with_overlay(
            original_path=original_path,
            output_path=output_path,
            overlay_x=overlay_x,
            overlay_y=overlay_y,
            frame_generator=frame_generator,
            total_frames=total_frames,
            original_info=original_info,
            crf=12  # High quality for chat overlays
        )
        
        logger.info(f"Successfully composed video with streaming overlay: {output_path}")
        
    except Exception as e:
        logger.error(f"Streaming composition failed: {e}")
        raise VideoCompositionError(f"Streaming composition failed: {e}") from e


def _calculate_overlay_dimensions_from_page(page: Page, config: ChannelConfig, original_info: VideoInfo) -> Tuple[int, int]:
    """
    Calculate overlay dimensions from page configuration.
    
    Args:
        page: Playwright page instance
        config: Channel configuration
        original_info: Original video information
        
    Returns:
        Tuple of (width, height) for the chat overlay
    """
    from vodloader.ffmpeg.utils import calculate_overlay_dimensions
    
    return calculate_overlay_dimensions(
        video_width=original_info.width,
        video_height=original_info.height,
        overlay_width=config.get_chat_overlay_width(),
        overlay_height=config.get_chat_overlay_height()
    )


async def verify_composition_requirements(
    original_path: Path,
    output_path: Path
) -> None:
    """
    Verify requirements for streaming composition.
    
    Args:
        original_path: Path to the original video file
        output_path: Path where the composite video will be saved
        
    Raises:
        VideoCompositionError: If requirements are not met
    """
    # Check input file exists
    if not original_path.exists():
        raise VideoCompositionError(f"Original video file not found: {original_path}")
    
    # Check output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check file size is reasonable
    original_size = original_path.stat().st_size
    
    if original_size == 0:
        raise VideoCompositionError(f"Original video file is empty: {original_path}")
    
    logger.info(f"Streaming composition requirements verified - Original: {original_size / (1024*1024):.1f}MB")