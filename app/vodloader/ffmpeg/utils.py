"""
Utility functions for FFmpeg operations.
"""

from typing import Tuple
import logging

logger = logging.getLogger('vodloader.ffmpeg.utils')


def calculate_overlay_position(
    original_width: int,
    original_height: int,
    overlay_width: int,
    overlay_height: int,
    position: str,
    padding: int = 10
) -> Tuple[int, int]:
    """
    Calculate overlay position coordinates.
    
    Args:
        original_width: Width of original video
        original_height: Height of original video
        overlay_width: Width of overlay
        overlay_height: Height of overlay
        position: Position string (top-left, top-right, bottom-left, bottom-right, left, right, center)
        padding: Padding from edges
        
    Returns:
        Tuple of (x, y) coordinates
    """
    position = position.lower().strip()
    
    # Calculate center positions
    center_x = (original_width - overlay_width) // 2
    center_y = (original_height - overlay_height) // 2
    
    # Position mapping
    positions = {
        'top-left': (padding, padding),
        'top-right': (original_width - overlay_width - padding, padding),
        'bottom-left': (padding, original_height - overlay_height - padding),
        'bottom-right': (
            original_width - overlay_width - padding,
            original_height - overlay_height - padding
        ),
        'left': (padding, center_y),
        'right': (original_width - overlay_width - padding, center_y),
        'center': (center_x, center_y),
        'top-center': (center_x, padding),
        'bottom-center': (center_x, original_height - overlay_height - padding)
    }
    
    if position in positions:
        x, y = positions[position]
    else:
        logger.warning(f"Invalid position '{position}', defaulting to top-left")
        x, y = positions['top-left']
    
    # Ensure coordinates are within bounds
    x = max(0, min(x, original_width - overlay_width))
    y = max(0, min(y, original_height - overlay_height))
    
    return x, y


def parse_frame_rate(frame_rate_str: str) -> float:
    """
    Parse frame rate string to float.
    
    Args:
        frame_rate_str: Frame rate as string (e.g., "30/1", "29.97")
        
    Returns:
        Frame rate as float
    """
    try:
        if '/' in frame_rate_str:
            num, den = frame_rate_str.split('/')
            return float(num) / float(den) if float(den) != 0 else 30.0
        else:
            return float(frame_rate_str)
    except (ValueError, ZeroDivisionError):
        logger.warning(f"Invalid frame rate '{frame_rate_str}', defaulting to 30.0")
        return 30.0


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (e.g., "1h 23m 45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.0f}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours}h {remaining_minutes}m {remaining_seconds:.0f}s"


def calculate_overlay_dimensions(
    video_width: int,
    video_height: int,
    overlay_width: int = None,
    overlay_height: int = None,
    width_ratio: float = 0.2,
    height_ratio: float = 0.4,
    min_width: int = 300,
    min_height: int = 400
) -> Tuple[int, int]:
    """
    Calculate overlay dimensions with fallback to ratios.
    
    Args:
        video_width: Original video width
        video_height: Original video height
        overlay_width: Explicit overlay width (optional)
        overlay_height: Explicit overlay height (optional)
        width_ratio: Width ratio of original video (fallback)
        height_ratio: Height ratio of original video (fallback)
        min_width: Minimum overlay width
        min_height: Minimum overlay height
        
    Returns:
        Tuple of (width, height) for overlay
    """
    if overlay_width and overlay_height:
        return overlay_width, overlay_height
    
    # Calculate based on ratios
    calculated_width = overlay_width or max(min_width, int(video_width * width_ratio))
    calculated_height = overlay_height or max(min_height, int(video_height * height_ratio))
    
    return calculated_width, calculated_height


def build_quality_args(
    preset: str = 'medium',
    crf: int = 23,
    video_codec: str = 'libx264',
    audio_codec: str = 'aac'
) -> list:
    """
    Build standard quality arguments for encoding.
    
    Args:
        preset: Encoding preset
        crf: Constant rate factor
        video_codec: Video codec
        audio_codec: Audio codec
        
    Returns:
        List of ffmpeg arguments
    """
    return [
        '-vcodec', video_codec,
        '-acodec', audio_codec,
        '-preset', preset,
        '-crf', str(crf),
        '-pix_fmt', 'yuv420p'
    ]