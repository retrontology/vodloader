"""
Video preprocessing for chat video generation.
"""

import asyncio
import functools
import logging
import subprocess
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
    
    async def preprocess_video(self, video: VideoFile) -> Tuple[Path, Optional[object]]:
        """
        Preprocess video by removing ads with cancellation support.
        
        Returns:
            Tuple of (processed_video_path, main_stream_properties)
        """
        processed_path = video.path
        main_stream_properties = None
        
        # Remove ads if requested
        if self.config.remove_ads and self.ad_detector:
            logger.info('Removing ads from video...')
            ad_free_path = video.path.parent.joinpath(f'{video.path.stem}.no_ads.mp4')
            
            try:
                # Run ad removal in executor to support cancellation
                loop = asyncio.get_event_loop()
                
                # Create process reference for cancellation support
                process_ref = {}
                
                # Create a partial function with the process reference
                remove_ads_with_ref = functools.partial(
                    self.ad_detector.remove_ads,
                    video.path,
                    ad_free_path,
                    process_ref
                )
                
                result = await loop.run_in_executor(None, remove_ads_with_ref)
                
                if result is not None:
                    processed_path, main_stream_properties = result
                    logger.info(f'Ad removal complete: {processed_path}')
                else:
                    logger.info('No ads detected, using original video')
                    
            except asyncio.CancelledError:
                logger.info("Ad removal cancelled")
                
                # Terminate any running process
                if 'process' in process_ref:
                    process = process_ref['process']
                    if process.poll() is None:
                        logger.info("Terminating ad removal process")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                
                # Clean up partial ad-free file if it exists
                if ad_free_path.exists():
                    ad_free_path.unlink()
                    logger.info(f"Cleaned up partial ad-free file: {ad_free_path}")
                raise
        
        return processed_path, main_stream_properties