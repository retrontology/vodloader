"""
Video compositor for chat overlay composition.

This module handles the composition of original stream videos with chat overlay videos
using FFmpeg. It supports configurable positioning, frame rate synchronization, and
quality preservation.
"""

import ffmpeg
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Tuple, Optional

from vodloader.models.ChannelConfig import ChannelConfig

logger = logging.getLogger('vodloader.post.chat.video_compositor')


class VideoCompositionError(Exception):
    """Raised when video composition fails."""
    pass


class FrameRateMismatchError(VideoCompositionError):
    """Raised when video frame rates don't match."""
    pass


async def get_video_info(video_path: Path) -> Dict:
    """
    Get video metadata including frame rate, dimensions, and duration.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dictionary containing video metadata
        
    Raises:
        VideoCompositionError: If video info cannot be retrieved
    """
    try:
        loop = asyncio.get_event_loop()
        
        def probe_video():
            return ffmpeg.probe(str(video_path))
        
        probe_data = await loop.run_in_executor(None, probe_video)
        
        # Find the video stream
        video_stream = None
        for stream in probe_data['streams']:
            if stream['codec_type'] == 'video':
                video_stream = stream
                break
        
        if not video_stream:
            raise VideoCompositionError(f"No video stream found in {video_path}")
        
        # Extract frame rate
        frame_rate_str = video_stream.get('r_frame_rate', '30/1')
        if '/' in frame_rate_str:
            num, den = frame_rate_str.split('/')
            frame_rate = float(num) / float(den)
        else:
            frame_rate = float(frame_rate_str)
        
        return {
            'width': int(video_stream['width']),
            'height': int(video_stream['height']),
            'frame_rate': frame_rate,
            'duration': float(video_stream.get('duration', 0)),
            'codec': video_stream.get('codec_name', 'unknown')
        }
        
    except Exception as e:
        raise VideoCompositionError(f"Failed to get video info for {video_path}: {e}")


def calculate_overlay_position(
    original_width: int,
    original_height: int,
    overlay_width: int,
    overlay_height: int,
    position: str,
    padding: int
) -> Tuple[int, int]:
    """
    Calculate the x,y coordinates for overlay positioning.
    
    Args:
        original_width: Width of the original video
        original_height: Height of the original video
        overlay_width: Width of the overlay video
        overlay_height: Height of the overlay video
        position: Position string (top-left, top-right, bottom-left, bottom-right, left, right)
        padding: Padding offset from edges
        
    Returns:
        Tuple of (x, y) coordinates for overlay positioning
    """
    # Calculate positions based on configuration
    if position == "top-left":
        x = padding
        y = padding
    elif position == "top-right":
        x = original_width - overlay_width - padding
        y = padding
    elif position == "bottom-left":
        x = padding
        y = original_height - overlay_height - padding
    elif position == "bottom-right":
        x = original_width - overlay_width - padding
        y = original_height - overlay_height - padding
    elif position == "left":
        x = padding
        y = (original_height - overlay_height) // 2
    elif position == "right":
        x = original_width - overlay_width - padding
        y = (original_height - overlay_height) // 2
    else:
        # Default to top-left if position is invalid
        logger.warning(f"Invalid position '{position}', defaulting to top-left")
        x = padding
        y = padding
    
    # Ensure coordinates are within bounds
    x = max(0, min(x, original_width - overlay_width))
    y = max(0, min(y, original_height - overlay_height))
    
    return x, y


async def composite_videos(
    original_path: Path,
    overlay_path: Path,
    output_path: Path,
    config: ChannelConfig
) -> None:
    """
    Composite original video with chat overlay ensuring frame rate synchronization.
    
    Args:
        original_path: Path to the original video file
        overlay_path: Path to the chat overlay video file
        output_path: Path where the composite video will be saved
        config: Channel configuration containing overlay settings
        
    Raises:
        VideoCompositionError: If composition fails
        FrameRateMismatchError: If video frame rates don't match
    """
    composition_start_time = time.time()
    
    logger.info(f"Starting video composition: {original_path} + {overlay_path} -> {output_path}")
    
    try:
        # Get video information for both files with detailed logging
        logger.debug("Analyzing input video files")
        original_info = await get_video_info(original_path)
        overlay_info = await get_video_info(overlay_path)
        
        logger.info(
            f"Original video: {original_info['width']}x{original_info['height']} "
            f"@ {original_info['frame_rate']:.2f}fps, {original_info['duration']:.1f}s, "
            f"codec: {original_info['codec']}"
        )
        logger.info(
            f"Overlay video: {overlay_info['width']}x{overlay_info['height']} "
            f"@ {overlay_info['frame_rate']:.2f}fps, {overlay_info['duration']:.1f}s, "
            f"codec: {overlay_info['codec']}"
        )
        
        # Check for frame rate compatibility and handle mismatches
        frame_rate_tolerance = 0.1  # Allow small differences due to floating point precision
        frame_rate_diff = abs(original_info['frame_rate'] - overlay_info['frame_rate'])
        
        # If frame rates don't match, we'll resample the overlay to match the original
        resample_overlay = frame_rate_diff > frame_rate_tolerance
        
        if resample_overlay:
            logger.info(
                f"Frame rate mismatch detected: original={original_info['frame_rate']:.2f}fps, "
                f"overlay={overlay_info['frame_rate']:.2f}fps (diff: {frame_rate_diff:.2f}fps). "
                f"Will resample overlay to match original frame rate."
            )
        else:
            logger.debug(f"Frame rates compatible (diff: {frame_rate_diff:.3f}fps)")
        
        # Verify duration compatibility (warning only)
        duration_diff = abs(original_info['duration'] - overlay_info['duration'])
        if duration_diff > 1.0:  # More than 1 second difference
            logger.warning(
                f"Duration mismatch: original={original_info['duration']:.1f}s, "
                f"overlay={overlay_info['duration']:.1f}s (diff: {duration_diff:.1f}s)"
            )
        
        # Calculate overlay position from configuration
        position = config.get_chat_position()
        padding = config.get_chat_padding()
        
        overlay_x, overlay_y = calculate_overlay_position(
            original_info['width'],
            original_info['height'],
            overlay_info['width'],
            overlay_info['height'],
            position,
            padding
        )
        
        logger.info(
            f"Positioning overlay at ({overlay_x}, {overlay_y}) "
            f"with position='{position}' and padding={padding}px"
        )
        
        # Validate overlay position is within bounds
        if (overlay_x + overlay_info['width'] > original_info['width'] or
            overlay_y + overlay_info['height'] > original_info['height']):
            logger.warning(
                f"Overlay extends beyond original video bounds: "
                f"overlay at ({overlay_x}, {overlay_y}) with size {overlay_info['width']}x{overlay_info['height']} "
                f"on {original_info['width']}x{original_info['height']} original"
            )
        
        # Create FFmpeg streams
        logger.debug("Creating FFmpeg streams")
        original_input = ffmpeg.input(str(original_path))
        overlay_input = ffmpeg.input(str(overlay_path))
        
        # Resample overlay frame rate if needed to match original
        if resample_overlay:
            logger.debug(f"Resampling overlay from {overlay_info['frame_rate']:.2f}fps to {original_info['frame_rate']:.2f}fps")
            overlay_input = ffmpeg.filter(overlay_input, 'fps', fps=original_info['frame_rate'])
        
        # Apply overlay filter with calculated position
        # The overlay filter composites the overlay video on top of the original
        # format=auto ensures proper alpha channel handling for transparency
        video_stream = ffmpeg.overlay(
            original_input['v'],  # Explicitly use video stream
            overlay_input,
            x=overlay_x,
            y=overlay_y,
            format='auto'  # Automatically handle alpha channel for transparency
        )
        
        # Preserve audio from original video
        audio_stream = original_input['a']
        
        # Configure output with quality preservation
        output_stream = ffmpeg.output(
            video_stream,
            audio_stream,
            str(output_path),
            vcodec='libx264',  # Use H.264 codec for compatibility
            acodec='copy',     # Copy audio stream without re-encoding
            preset='medium',   # Balance between speed and compression
            crf=18,           # High quality (lower CRF = higher quality)
            pix_fmt='yuv420p' # Ensure compatibility with most players
        )
        
        # Overwrite output file if it exists
        output_stream = ffmpeg.overwrite_output(output_stream)
        
        # Run composition in executor to avoid blocking
        logger.info("Starting FFmpeg composition process")
        loop = asyncio.get_event_loop()
        
        def run_composition():
            try:
                ffmpeg.run(output_stream, quiet=True, capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                # Re-raise with captured stderr
                raise e
        
        # Run with timeout to prevent hanging
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, run_composition),
                timeout=300.0  # 5 minute timeout for composition
            )
        except asyncio.TimeoutError:
            logger.error("Video composition timed out after 5 minutes")
            raise VideoCompositionError("Video composition timed out")
        
        composition_duration = time.time() - composition_start_time
        
        # Verify output file was created
        if not output_path.exists():
            raise VideoCompositionError(f"Output file was not created: {output_path}")
        
        # Check output file size
        output_size = output_path.stat().st_size
        if output_size == 0:
            raise VideoCompositionError(f"Output file is empty: {output_path}")
        
        # Get final video info for logging
        try:
            final_info = await get_video_info(output_path)
            logger.info(
                f"Successfully composed video: {final_info['width']}x{final_info['height']} "
                f"@ {final_info['frame_rate']:.2f}fps, "
                f"size: {output_size / (1024*1024):.1f}MB, "
                f"duration: {composition_duration:.1f}s"
            )
        except Exception as info_error:
            # Don't fail if we can't get final info, just log the basic success
            logger.info(
                f"Successfully composed video: {output_path} "
                f"({output_size / (1024*1024):.1f}MB) in {composition_duration:.1f}s"
            )
            logger.debug(f"Could not retrieve final video info: {info_error}")
        
    except ffmpeg.Error as e:
        # Extract stderr for better error reporting
        stderr = e.stderr.decode('utf-8') if e.stderr else 'No error details available'
        composition_duration = time.time() - composition_start_time
        
        logger.error(
            f"FFmpeg error during composition after {composition_duration:.1f}s: {stderr}"
        )
        raise VideoCompositionError(f"FFmpeg error during composition: {stderr}")
    except (FrameRateMismatchError, VideoCompositionError):
        # Re-raise these specific errors as-is
        raise
    except Exception as e:
        composition_duration = time.time() - composition_start_time
        logger.error(f"Unexpected error during video composition after {composition_duration:.1f}s: {e}")
        raise VideoCompositionError(f"Unexpected error during video composition: {e}") from e


async def verify_composition_requirements(
    original_path: Path,
    overlay_path: Path,
    output_path: Path
) -> None:
    """
    Verify that all requirements for video composition are met.
    
    Args:
        original_path: Path to the original video file
        overlay_path: Path to the chat overlay video file
        output_path: Path where the composite video will be saved
        
    Raises:
        VideoCompositionError: If requirements are not met
    """
    # Check input files exist
    if not original_path.exists():
        raise VideoCompositionError(f"Original video file not found: {original_path}")
    
    if not overlay_path.exists():
        raise VideoCompositionError(f"Overlay video file not found: {overlay_path}")
    
    # Check output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check file sizes are reasonable
    original_size = original_path.stat().st_size
    overlay_size = overlay_path.stat().st_size
    
    if original_size == 0:
        raise VideoCompositionError(f"Original video file is empty: {original_path}")
    
    if overlay_size == 0:
        raise VideoCompositionError(f"Overlay video file is empty: {overlay_path}")
    
    logger.info(f"Composition requirements verified - Original: {original_size / (1024*1024):.1f}MB, Overlay: {overlay_size / (1024*1024):.1f}MB")