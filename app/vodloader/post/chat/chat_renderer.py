"""
Chat renderer for message processing and video generation.

This module provides the ChatRenderer class that processes Twitch chat messages,
generates HTML/CSS/JS for browser rendering, implements deterministic message
positioning, and handles video recording with transparent backgrounds.
"""

import asyncio
import json
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator

from vodloader.ffmpeg import probe_video
from playwright.async_api import Page

from vodloader.models import Message, ChannelConfig, VideoFile
from .template_manager import TemplateManager, TemplateError

logger = logging.getLogger('vodloader.chat_video.chat_renderer')


class ChatRendererError(Exception):
    """Base exception for chat renderer errors."""
    pass


class VideoMetadataError(ChatRendererError):
    """Exception raised when video metadata extraction fails."""
    pass


class ChatRenderer:
    """
    Processes chat messages and generates video with transparent background.
    
    Handles deterministic message positioning based on timestamps, video metadata
    extraction for frame rate matching, and transparent background video recording.
    """
    
    def __init__(self, messages: List[Message], config: ChannelConfig, video_info: Dict[str, Any]):
        """
        Initialize renderer with messages, configuration, and video metadata.
        
        Args:
            messages: List of Message objects to render
            config: ChannelConfig with chat overlay settings
            video_info: Dictionary containing video metadata (frame_rate, duration, etc.)
        """
        self.messages = messages
        self.config = config
        self.video_info = video_info
        self.template_dir = Path(__file__).parent.parent / "chat_templates"
        
        # Initialize template manager
        try:
            self.template_manager = TemplateManager(self.template_dir)
        except TemplateError as e:
            raise ChatRendererError(f"Template manager initialization failed: {e}") from e
        
        # Validate inputs
        if not self.messages:
            raise ChatRendererError("No messages provided for rendering")
        
        logger.info(f"ChatRenderer initialized with {len(self.messages)} messages")
        logger.debug(f"Video info: {self.video_info}")
    
    @classmethod
    async def extract_video_metadata(cls, video_file: VideoFile) -> Dict[str, Any]:
        """
        Extract video metadata for frame rate matching.
        
        Args:
            video_file: VideoFile instance to analyze
            
        Returns:
            Dictionary containing video metadata including frame_rate, duration, width, height
            
        Raises:
            VideoMetadataError: If metadata extraction fails
        """
        try:
            # Use async probe to avoid event loop conflicts
            from vodloader.ffmpeg.adapters import legacy_ffmpeg
            probe_info = await legacy_ffmpeg.async_probe(video_file.path if not video_file.transcode_path else video_file.transcode_path)
            
            if not probe_info or 'streams' not in probe_info:
                raise VideoMetadataError("No stream information found in video")
            
            # Find the video stream
            video_stream = None
            for stream in probe_info['streams']:
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise VideoMetadataError("No video stream found in file")
            
            # Extract frame rate
            frame_rate = cls._extract_frame_rate(video_stream)
            
            # Extract other metadata
            duration = float(video_stream.get('duration', 0))
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            
            if duration <= 0:
                # Try to get duration from format info
                if 'format' in probe_info and 'duration' in probe_info['format']:
                    duration = float(probe_info['format']['duration'])
            
            metadata = {
                'frame_rate': frame_rate,
                'duration': duration,
                'width': width,
                'height': height,
                'codec': video_stream.get('codec_name', 'unknown'),
                'pixel_format': video_stream.get('pix_fmt', 'unknown')
            }
            
            logger.info(f"Extracted video metadata: {frame_rate}fps, {duration}s, {width}x{height}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract video metadata: {e}")
            raise VideoMetadataError(f"Video metadata extraction failed: {e}") from e
    
    @staticmethod
    def _extract_frame_rate(video_stream: Dict[str, Any]) -> float:
        """
        Extract frame rate from video stream information.
        
        Args:
            video_stream: Video stream dictionary from ffprobe
            
        Returns:
            Frame rate as float (fps)
        """
        # Try r_frame_rate first (more accurate)
        if 'r_frame_rate' in video_stream:
            r_frame_rate = video_stream['r_frame_rate']
            if isinstance(r_frame_rate, str) and '/' in r_frame_rate:
                num, den = map(int, r_frame_rate.split('/'))
                if den > 0:
                    return num / den
            elif isinstance(r_frame_rate, (int, float)):
                return float(r_frame_rate)
        
        # Fallback to avg_frame_rate
        if 'avg_frame_rate' in video_stream:
            avg_frame_rate = video_stream['avg_frame_rate']
            if isinstance(avg_frame_rate, str) and '/' in avg_frame_rate:
                num, den = map(int, avg_frame_rate.split('/'))
                if den > 0:
                    return num / den
            elif isinstance(avg_frame_rate, (int, float)):
                return float(avg_frame_rate)
        
        # Default fallback
        logger.warning("Could not determine frame rate, using default 30fps")
        return 30.0
    
    def calculate_overlay_dimensions(self) -> Tuple[int, int]:
        """
        Calculate overlay dimensions based on configuration and video dimensions.
        
        Returns:
            Tuple of (width, height) for the chat overlay
        """
        # Use explicit dimensions if provided
        overlay_width = self.config.get_chat_overlay_width()
        overlay_height = self.config.get_chat_overlay_height()
        
        if overlay_width and overlay_height:
            return overlay_width, overlay_height
        
        # Calculate default dimensions based on video size
        video_width = self.video_info.get('width', 1920)
        video_height = self.video_info.get('height', 1080)
        
        # Default to 20% of video width, 40% of video height
        if not overlay_width:
            overlay_width = max(300, int(video_width * 0.2))
        
        if not overlay_height:
            overlay_height = max(400, int(video_height * 0.4))
        
        logger.debug(f"Calculated overlay dimensions: {overlay_width}x{overlay_height}")
        return overlay_width, overlay_height
    
    def prepare_message_data(self, video_start_time: datetime) -> List[Dict[str, Any]]:
        """
        Prepare message data for JavaScript injection with timing offsets.
        
        Args:
            video_start_time: Start time of the video for calculating offsets
            
        Returns:
            List of message dictionaries with timestamp offsets from video start
        """
        message_data = []
        
        for message in self.messages:
            # Calculate offset from video start in seconds
            time_offset = (message.timestamp - video_start_time).total_seconds()
            
            # Skip messages that occur before video start
            if time_offset < 0:
                continue
            
            # Skip messages that occur after video end
            if time_offset > self.video_info.get('duration', float('inf')):
                continue
            
            message_dict = {
                'id': message.id,
                'username': message.display_name,
                'text': message.content or '',
                'color': message.color,
                'timestamp': time_offset,  # Offset in seconds from video start
                'badges': message.parse_badges() or [],
                'moderator': message.moderator,
                'subscriber': message.subscriber,
                'first_message': message.first_message
            }
            
            message_data.append(message_dict)
        
        # Sort by timestamp to ensure proper ordering
        message_data.sort(key=lambda x: x['timestamp'])
        
        logger.info(f"Prepared {len(message_data)} messages for rendering")
        return message_data
    
    def _build_template_config(self) -> Dict[str, Any]:
        """
        Build configuration dictionary for template manager.
        
        Returns:
            Dictionary containing all configuration values for template generation
        """
        overlay_width, overlay_height = self.calculate_overlay_dimensions()
        
        return {
            'font_family': self.config.get_chat_font_family(),
            'font_size': self.config.get_chat_font_size(),
            'font_style': self.config.get_chat_font_style(),
            'font_weight': self.config.get_chat_font_weight(),
            'text_color': self.config.get_chat_text_color(),
            'text_shadow_color': self.config.get_chat_text_shadow_color(),
            'text_shadow_size': self.config.get_chat_text_shadow_size(),
            'overlay_width': overlay_width,
            'overlay_height': overlay_height,
            'position': self.config.get_chat_position(),
            'padding': self.config.get_chat_padding(),
            'message_duration': self.config.get_chat_message_duration(),
            'frame_rate': self.video_info.get('frame_rate', 30.0),
            'video_duration': self.video_info.get('duration', 0),
            'show_timestamps': False  # Can be made configurable later
        }
    
    async def generate_html_content(self, video_start_time: datetime) -> str:
        """
        Generate complete HTML content with injected data using template manager.
        
        Args:
            video_start_time: Start time of the video for message timing
            
        Returns:
            Complete HTML string ready for browser loading
        """
        try:
            # Prepare message data
            message_data = self.prepare_message_data(video_start_time)
            
            # Build configuration for template manager
            template_config = self._build_template_config()
            
            # Generate complete HTML using template manager
            html_content = self.template_manager.generate_complete_html(
                messages=message_data,
                config=template_config,
                use_cache=True
            )
            
            logger.debug("Generated HTML content with template manager")
            return html_content
            
        except TemplateError as e:
            logger.error(f"Template generation failed: {e}")
            raise ChatRendererError(f"HTML generation failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to generate HTML content: {e}")
            raise ChatRendererError(f"HTML generation failed: {e}") from e
    
    async def prepare_for_streaming(self, page: Page) -> None:
        """
        Prepare the page for streaming frame generation.
        
        Args:
            page: Playwright page instance for rendering
            
        Raises:
            ChatRendererError: If page preparation fails
        """
        try:
            logger.info(f"Preparing page for streaming with {len(self.messages)} messages")
            
            # Determine video start time
            video_start_time = self.messages[0].timestamp if self.messages else datetime.now()
            logger.debug(f"Video start time: {video_start_time}")
            
            # Generate and load HTML content
            logger.debug("Generating HTML content for streaming")
            html_content = await self.generate_html_content(video_start_time)
            
            # Load content into page with timeout monitoring
            logger.debug("Loading HTML content into browser page")
            try:
                await asyncio.wait_for(
                    page.set_content(html_content, wait_until='networkidle'),
                    timeout=30.0  # 30 second timeout for page load
                )
            except asyncio.TimeoutError:
                raise ChatRendererError("Page content loading timed out")
            
            # Wait for fonts to load
            logger.debug("Waiting for fonts to load")
            await page.wait_for_timeout(2000)
            
            # Initialize chat overlay
            logger.debug("Initializing chat overlay in browser")
            await page.evaluate("window.AUTOMATION_MODE = true;")
            await page.evaluate("window.initializeChatOverlay();")
            
            logger.info("Page prepared successfully for streaming")
            
        except ChatRendererError:
            raise
        except Exception as e:
            logger.error(f"Failed to prepare page for streaming: {e}")
            raise ChatRendererError(f"Page preparation failed: {e}") from e
    
    def clear_template_cache(self) -> None:
        """
        Clear the template cache to force reload of template files.
        
        Useful for development or when template files have been updated.
        """
        self.template_manager.clear_cache()
        logger.debug("Template cache cleared")
    
    def get_template_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the template cache.
        
        Returns:
            Dictionary with cache statistics and information
        """
        return self.template_manager.get_cache_info()
    
    async def generate_frame_stream(self, page: Page) -> AsyncGenerator[bytes, None]:
        """
        Generate chat overlay frames as an async stream for direct composition.
        
        This method yields PNG frame bytes without storing them on disk,
        enabling memory-efficient streaming composition.
        
        Args:
            page: Playwright page instance for rendering (should be prepared with prepare_for_streaming)
            
        Yields:
            PNG frame bytes for each timestamp
            
        Raises:
            ChatRendererError: If frame generation fails
        """
        try:
            # Get video parameters
            frame_rate = self.video_info.get('frame_rate', 30.0)
            duration = self.video_info.get('duration', 0)
            
            if duration <= 0:
                raise ChatRendererError(f"Invalid video duration: {duration}")
            
            total_frames = int(duration * frame_rate)
            logger.info(f"Generating {total_frames} frames at {frame_rate}fps for streaming")
            
            # Generate frames as stream
            for frame_num in range(total_frames):
                timestamp = frame_num / frame_rate
                
                try:
                    # Render chat at this timestamp
                    await page.evaluate(f"window.renderChatAtTimestamp({timestamp});")
                    
                    # Wait for rendering to complete
                    await page.wait_for_timeout(50)
                    
                    # Capture frame as bytes
                    frame_bytes = await page.screenshot(
                        full_page=True,
                        omit_background=True,
                        type='png'
                    )
                    
                    # Yield frame bytes for streaming
                    yield frame_bytes
                    
                except Exception as frame_error:
                    logger.warning(f"Failed to generate frame {frame_num}: {frame_error}")
                    # Continue to next frame on error
                    continue
            
            logger.info("Frame stream generation complete")
            
        except ChatRendererError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate frame stream: {e}")
            raise ChatRendererError(f"Frame stream generation failed: {e}") from e
    
