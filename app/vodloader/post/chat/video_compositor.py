"""
Video compositor for chat overlay composition.

This module handles the composition of original stream videos with chat overlay videos
using FFmpeg. It supports configurable positioning, frame rate synchronization, and
quality preservation. Includes streaming composition for direct frame-to-frame processing.
"""

import ffmpeg
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, AsyncGenerator

from vodloader.models.ChannelConfig import ChannelConfig
from playwright.async_api import Page

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
    page: Page,
    output_path: Path,
    config: ChannelConfig,
    frame_generator: AsyncGenerator[bytes, None],
    total_frames: int
) -> None:
    """
    Composite original video with streaming chat overlay frames directly.
    
    This method eliminates the need for intermediate overlay video files by
    streaming chat frames directly into the composition process.
    
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
    composition_start_time = time.time()
    
    logger.info(f"Starting streaming video composition: {original_path} -> {output_path}")
    
    try:
        # Get original video information
        logger.debug("Analyzing original video file")
        original_info = await get_video_info(original_path)
        
        logger.info(
            f"Original video: {original_info['width']}x{original_info['height']} "
            f"@ {original_info['frame_rate']:.2f}fps, {original_info['duration']:.1f}s, "
            f"codec: {original_info['codec']}"
        )
        
        # Calculate overlay dimensions and position
        overlay_width, overlay_height = _calculate_overlay_dimensions_from_page(page, config, original_info)
        position = config.get_chat_position()
        padding = config.get_chat_padding()
        
        overlay_x, overlay_y = calculate_overlay_position(
            original_info['width'],
            original_info['height'],
            overlay_width,
            overlay_height,
            position,
            padding
        )
        
        logger.info(
            f"Streaming overlay: {overlay_width}x{overlay_height} at ({overlay_x}, {overlay_y}) "
            f"with position='{position}' and padding={padding}px"
        )
        
        # Create FFmpeg process for streaming composition
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            # Original video input
            '-i', str(original_path),
            # Overlay frames input (streaming)
            '-f', 'image2pipe',
            '-vcodec', 'png',
            '-r', str(original_info['frame_rate']),
            '-i', '-',  # Read overlay frames from stdin
            # Apply overlay filter
            '-filter_complex', f'[0:v][1:v]overlay={overlay_x}:{overlay_y}:eof_action=pass[v]',
            # Map streams
            '-map', '[v]',
            '-map', '0:a',  # Copy audio from original
            # Output settings
            '-vcodec', 'libx264',
            '-acodec', 'copy',
            '-preset', 'medium',
            '-crf', '12',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
        
        logger.debug(f"Starting streaming FFmpeg process: {' '.join(ffmpeg_cmd)}")
        
        # Start FFmpeg process
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            # Stream overlay frames to FFmpeg
            frame_count = 0
            async for frame_bytes in frame_generator:
                if process.stdin:
                    process.stdin.write(frame_bytes)
                    await process.stdin.drain()
                
                frame_count += 1
                
                # Log progress periodically
                if total_frames > 100 and frame_count % (total_frames // 10) == 0:
                    progress = (frame_count / total_frames) * 100
                    elapsed = time.time() - composition_start_time
                    estimated_total = elapsed / frame_count * total_frames
                    remaining = estimated_total - elapsed
                    
                    logger.info(
                        f"Composition progress: {progress:.1f}% ({frame_count}/{total_frames} frames, "
                        f"~{remaining:.0f}s remaining)"
                    )
            
            # Close stdin to signal end of overlay input
            if process.stdin:
                process.stdin.close()
                await process.stdin.wait_closed()
            
            logger.info(f"Streamed {frame_count} overlay frames to composition")
            
        except Exception as streaming_error:
            # Terminate FFmpeg process if streaming fails
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            raise streaming_error
        
        # Wait for FFmpeg to finish processing
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown ffmpeg error"
            logger.error(f"FFmpeg failed with return code {process.returncode}: {error_msg}")
            raise VideoCompositionError(f"Streaming composition failed: {error_msg}")
        
        composition_duration = time.time() - composition_start_time
        
        # Verify output file was created
        if not output_path.exists():
            raise VideoCompositionError(f"Output file was not created: {output_path}")
        
        output_size = output_path.stat().st_size
        if output_size == 0:
            raise VideoCompositionError(f"Output file is empty: {output_path}")
        
        logger.info(
            f"Successfully composed video with streaming overlay: {output_path} "
            f"({output_size / (1024*1024):.1f}MB) in {composition_duration:.1f}s"
        )
        
    except VideoCompositionError:
        raise
    except Exception as e:
        composition_duration = time.time() - composition_start_time
        logger.error(f"Unexpected error during streaming composition after {composition_duration:.1f}s: {e}")
        raise VideoCompositionError(f"Unexpected error during streaming composition: {e}") from e


def _calculate_overlay_dimensions_from_page(page: Page, config: ChannelConfig, original_info: Dict) -> Tuple[int, int]:
    """
    Calculate overlay dimensions from page configuration.
    
    Args:
        page: Playwright page instance
        config: Channel configuration
        original_info: Original video information
        
    Returns:
        Tuple of (width, height) for the chat overlay
    """
    # Use explicit dimensions if provided
    overlay_width = config.get_chat_overlay_width()
    overlay_height = config.get_chat_overlay_height()
    
    if overlay_width and overlay_height:
        return overlay_width, overlay_height
    
    # Calculate default dimensions based on video size
    video_width = original_info.get('width', 1920)
    video_height = original_info.get('height', 1080)
    
    # Default to 20% of video width, 40% of video height
    if not overlay_width:
        overlay_width = max(300, int(video_width * 0.2))
    
    if not overlay_height:
        overlay_height = max(400, int(video_height * 0.4))
    
    logger.debug(f"Calculated overlay dimensions: {overlay_width}x{overlay_height}")
    return overlay_width, overlay_height


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