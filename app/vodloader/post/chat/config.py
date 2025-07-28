"""
Configuration for chat video generation.
"""

from datetime import timedelta
from typing import Optional, Tuple
from multiprocessing import cpu_count


class ChatVideoConfig:
    """Configuration for chat video generation."""
    
    def __init__(
        self,
        width: int = 320,
        height: Optional[int] = None,
        x_offset: int = 20,
        y_offset: int = 20,
        padding: int = 20,
        font_family: str = "FreeSans",
        font_style: str = "Regular", 
        font_size: int = 24,
        font_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
        background_color: Tuple[int, int, int, int] = (0, 0, 0, 127),
        message_duration: int = 10,
        remove_ads: bool = True,
        use_gpu: bool = True,
        batch_size: int = 30,
        num_workers: Optional[int] = None
    ):
        self.width = width
        self.height = height
        self.x_offset = x_offset  # Distance from left edge of video
        self.y_offset = y_offset  # Distance from top edge of video
        self.padding = padding    # Internal padding within chat area
        self.font_family = font_family
        self.font_style = font_style
        self.font_size = font_size
        self.font_color = font_color
        self.background_color = background_color
        self.message_duration = timedelta(seconds=message_duration)
        self.remove_ads = remove_ads
        self.use_gpu = use_gpu
        self.batch_size = batch_size
        self.num_workers = num_workers or min(cpu_count(), 8)