"""
Chat area positioning and sizing.
"""

import logging
from typing import Tuple

from .config import ChatVideoConfig

logger = logging.getLogger('vodloader.chat_video.area')


class ChatArea:
    """Represents the chat overlay area with proper positioning."""
    
    def __init__(self, config: ChatVideoConfig, video_width: int, video_height: int):
        self.config = config
        self.video_width = video_width
        self.video_height = video_height
        
        # Auto-size chat area to fit within video bounds
        self.width, self.height = self._calculate_optimal_dimensions(config, video_width, video_height)
        
        # Chat area position (top-left corner of chat area)
        self.x = config.x_offset
        self.y = config.y_offset
        
        # Content area (inside padding)
        self.content_x = self.x + config.padding
        self.content_y = self.y + config.padding
        self.content_width = self.width - (config.padding * 2)
        self.content_height = self.height - (config.padding * 2)
        
        # Maximum Y coordinate for content
        self.max_content_y = self.content_y + self.content_height
    
    def _calculate_optimal_dimensions(self, config: ChatVideoConfig, video_width: int, video_height: int) -> Tuple[int, int]:
        """Calculate optimal chat area dimensions that fit within video bounds."""
        # Start with configured or default dimensions
        width = config.width
        height = config.height
        
        # Calculate maximum available space
        max_width = video_width - config.x_offset
        max_height = video_height - config.y_offset
        
        # Auto-size width if it exceeds bounds
        if width > max_width:
            width = max_width
            logger.info(f'Auto-sizing chat width from {config.width} to {width} to fit video bounds')
        
        # Auto-size height if not specified or if it exceeds bounds
        if height is None:
            # Default to a reasonable portion of video height
            height = min(video_height // 2, max_height)
            logger.info(f'Auto-sizing chat height to {height} (50% of video height or max available)')
        elif height > max_height:
            height = max_height
            logger.info(f'Auto-sizing chat height from {config.height} to {height} to fit video bounds')
        
        # Ensure minimum dimensions for usability
        min_width = 200
        min_height = 100
        
        width = max(width, min_width)
        height = max(height, min_height)
        
        return width, height
    
    def fits_in_video(self) -> bool:
        """Check if chat area fits within video bounds."""
        return (self.x + self.width <= self.video_width and 
                self.y + self.height <= self.video_height)