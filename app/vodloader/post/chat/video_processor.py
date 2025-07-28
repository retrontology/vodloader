"""
Video preprocessing for chat video generation.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from vodloader.models import VideoFile
from ..ad_detection import AdDetector
from .config import ChatVideoConfig

logger = logging.getLogger('vodloader.chat_video.video_processor')


class VideoProcessor:
    """Handles video preprocessing (ad removal, trimming)."""
    
    def __init__(self, config: ChatVideoConfig):
        self.config = config
        self.ad_detector = AdDetector() if config.remove_ads else None
    
    def preprocess_video(self, video: VideoFile) -> Tuple[Path, Optional[object]]:
        """
        Preprocess video by removing ads.
        
        Returns:
            Tuple of (processed_video_path, main_stream_properties)
        """
        processed_path = video.path
        main_stream_properties = None
        
        # Remove ads if requested
        if self.config.remove_ads and self.ad_detector:
            logger.info('Removing ads from video...')
            ad_free_path = video.path.parent.joinpath(f'{video.path.stem}.no_ads.mp4')
            result = self.ad_detector.remove_ads(video.path, ad_free_path)
            
            if result is not None:
                processed_path, main_stream_properties = result
                logger.info(f'Ad removal complete: {processed_path}')
            else:
                logger.info('No ads detected, using original video')
        
        return processed_path, main_stream_properties