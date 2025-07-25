"""
Chat video generation for Twitch VODs.

This module provides functionality to overlay chat messages on video streams
with proper timing and formatting.
"""

import cv2
import ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import timedelta, timezone
from typing import List, Optional, Tuple
import logging

from vodloader.models import VideoFile, Message
from .ad_detection import AdDetector
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font

logger = logging.getLogger('vodloader.chat_video')


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
        trim_offset: int = 30,
        remove_ads: bool = True
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
        self.trim_offset = trim_offset
        self.remove_ads = remove_ads


class FontManager:
    """Manages font loading and caching."""
    
    _font_cache = {}
    
    @classmethod
    def get_fonts(cls) -> List[FT2Font]:
        """Returns a list of all available fonts on the system."""
        system_fonts = font_manager.findSystemFonts(fontext='ttf')
        fonts = []
        for font in system_fonts:
            try:
                fonts.append(font_manager.get_font(font))
            except Exception as e:
                logger.warning(f'Failed to load font from {font}: {e}')
        return fonts
    
    @classmethod
    def get_font(
        cls,
        font_family: str = "FreeSans",
        font_style: str = "Regular",
        font_size: int = 24,
    ) -> ImageFont.FreeTypeFont:
        """
        Returns a font object for the specified font family, style, and size.
        Uses caching to avoid reloading fonts.
        """
        cache_key = (font_family, font_style, font_size)
        
        if cache_key in cls._font_cache:
            return cls._font_cache[cache_key]
        
        font = None
        for font_obj in cls.get_fonts():
            if font_obj.family_name == font_family and font_obj.style_name == font_style:
                font = font_obj
                break
        
        if not font:
            raise ValueError(f'Font {font_family} {font_style} not found')
        
        font_instance = ImageFont.truetype(font.fname, font_size)
        cls._font_cache[cache_key] = font_instance
        return font_instance


class VideoProcessor:
    """Handles video preprocessing (ad removal, trimming)."""
    
    def __init__(self, config: ChatVideoConfig):
        self.config = config
        self.ad_detector = AdDetector() if config.remove_ads else None
    
    def preprocess_video(self, video: VideoFile) -> Tuple[Path, Optional[object]]:
        """
        Preprocess video by removing ads and trimming.
        
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
        
        # Trim the processed video
        trim_path = video.path.parent.joinpath(f'{video.path.stem}.trim.mp4')
        trim_video = ffmpeg.input(str(processed_path), ss=self.config.trim_offset)
        trim_video = ffmpeg.output(trim_video, str(trim_path), vcodec='copy')
        trim_video = ffmpeg.overwrite_output(trim_video)
        ffmpeg.run(trim_video, quiet=True)
        
        # Clean up ad-free file if it was created and different from original
        if self.config.remove_ads and processed_path != video.path:
            processed_path.unlink()
        
        return trim_path, main_stream_properties


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


class ChatRenderer:
    """Handles chat message rendering on video frames."""
    
    def __init__(self, config: ChatVideoConfig):
        self.config = config
        self.font = FontManager.get_font(
            config.font_family,
            config.font_style, 
            config.font_size
        )
        self.line_height = config.font_size * 1.2
        self.chat_area = None
    
    def setup_chat_area(self, video_width: int, video_height: int) -> ChatArea:
        """Setup the chat area for the given video dimensions."""
        self.chat_area = ChatArea(self.config, video_width, video_height)
        
        logger.info(f'Chat area: {self.chat_area.width}x{self.chat_area.height} '
                   f'at ({self.chat_area.x}, {self.chat_area.y}) '
                   f'for video {video_width}x{video_height}')
        
        return self.chat_area
    
    def render_messages_on_frame(
        self,
        frame: np.ndarray,
        messages: List[Message],
        current_time: timedelta,
        message_index: int
    ) -> np.ndarray:
        """Render chat messages on a single frame."""
        if not self.chat_area:
            raise ValueError("Chat area not initialized. Call setup_chat_area first.")
        
        base_image = Image.fromarray(frame, mode="RGB")
        draw = ImageDraw.Draw(base_image)
        
        # Get visible messages (newest first)
        visible_messages = []
        visible_message_index = message_index
        
        while visible_message_index >= 0:
            message = messages[visible_message_index]
            message_time = message.timestamp
            if message_time.tzinfo is None:
                message_time = message_time.replace(tzinfo=timezone.utc)
            
            if (current_time - message_time) > self.config.message_duration:
                break
            
            visible_messages.append(message)
            visible_message_index -= 1
        
        if not visible_messages:
            return np.array(base_image)
        
        # Render messages from bottom up (newer messages at bottom)
        current_y = self.chat_area.max_content_y
        max_lines = int(self.chat_area.content_height // self.line_height)
        lines_used = 0
        
        for message in visible_messages:
            if lines_used >= max_lines:
                break
            
            # Calculate how many lines this message needs
            message_lines = self._wrap_message(draw, message)
            lines_available = max_lines - lines_used
            
            # Show as many lines as we can fit (partial if needed)
            lines_to_show = min(len(message_lines), lines_available)
            if lines_to_show <= 0:
                break
            
            # If truncated, show the LAST lines instead of first lines
            if lines_to_show < len(message_lines):
                # Take the last N lines
                lines_to_render = message_lines[-lines_to_show:]
                is_truncated = True
            else:
                # Show all lines
                lines_to_render = message_lines
                is_truncated = False
            
            # Render from bottom up
            for i in range(len(lines_to_render) - 1, -1, -1):
                current_y -= self.line_height
                # For truncated messages, only the last line gets the prefix
                show_prefix = (i == len(lines_to_render) - 1) if is_truncated else (i == 0)
                self._draw_message_line(draw, message, lines_to_render[i], current_y, show_prefix)
                lines_used += 1
        
        return np.array(base_image)
    
    def _wrap_message(self, draw: ImageDraw.Draw, message: Message) -> List[str]:
        """Wrap message text into lines that fit the chat width."""
        prefix = f'{message.display_name}: '
        content = message.content
        
        # Calculate available widths
        prefix_width = draw.textlength(prefix, font=self.font)
        first_line_width = self.chat_area.content_width - prefix_width
        full_line_width = self.chat_area.content_width
        
        words = content.split(' ')
        lines = []
        current_line = []
        available_width = first_line_width
        
        for word in words:
            word_width = draw.textlength(f' {word}' if current_line else word, font=self.font)
            
            if word_width <= available_width:
                current_line.append(word)
                available_width -= word_width
            else:
                # Start new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                available_width = full_line_width - draw.textlength(word, font=self.font)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else ['']
    
    def _draw_message_line(self, draw: ImageDraw.Draw, message: Message, line: str, y: int, is_first_line: bool):
        """Draw a single line of a message."""
        if is_first_line:
            # Draw prefix + first line
            prefix = f'{message.display_name}: '
            draw.text(
                (self.chat_area.content_x, y),
                prefix,
                font=self.font,
                fill=message.color,
                stroke_fill=self.config.background_color,
                stroke_width=2
            )
            
            prefix_width = draw.textlength(prefix, font=self.font)
            x_pos = self.chat_area.content_x + prefix_width
        else:
            # Draw continuation line
            x_pos = self.chat_area.content_x
        
        if line:
            draw.text(
                (x_pos, y),
                line,
                font=self.font,
                fill=self.config.font_color,
                stroke_fill=self.config.background_color,
                stroke_width=2
            )


class ChatVideoGenerator:
    """Main class for generating chat overlay videos."""
    
    def __init__(self, config: Optional[ChatVideoConfig] = None):
        self.config = config or ChatVideoConfig()
        self.video_processor = VideoProcessor(self.config)
        self.chat_renderer = ChatRenderer(self.config)
    
    async def generate(self, video: VideoFile) -> Optional[Path]:
        """
        Generate a chat overlay video.
        
        Args:
            video: The video file to process
            
        Returns:
            Path to the generated video, or None if no messages found
        """
        logger.info(f'Generating chat video for {video.path}')
        
        # Get messages for this video
        messages = await Message.for_video(video)
        if len(messages) == 0:
            logger.info('No messages found for this video')
            return None
        
        logger.info(f'Found {len(messages)} messages')
        
        # Preprocess video (ad removal, trimming)
        trim_path, main_stream_properties = self.video_processor.preprocess_video(video)
        
        try:
            # Process the video
            return await self._process_video(
                video, trim_path, messages, main_stream_properties
            )
        finally:
            # Clean up trimmed file
            if trim_path.exists():
                trim_path.unlink()
    
    async def _process_video(
        self,
        video: VideoFile,
        trim_path: Path,
        messages: List[Message],
        main_stream_properties: Optional[object]
    ) -> Path:
        """Process the video with chat overlay."""
        # Open input video
        video_in = cv2.VideoCapture(str(trim_path), apiPreference=cv2.CAP_FFMPEG)
        
        # Get video properties
        video_width = int(video_in.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(video_in.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = video_in.get(cv2.CAP_PROP_FPS)
        
        # Use main stream properties if available
        if main_stream_properties:
            logger.info(f'Using main stream properties: {main_stream_properties.width}x{main_stream_properties.height} @ {main_stream_properties.fps}fps')
            video_width = main_stream_properties.width
            video_height = main_stream_properties.height
            fps = main_stream_properties.fps
        
        # Setup chat area
        chat_area = self.chat_renderer.setup_chat_area(video_width, video_height)
        
        # Open output video
        chat_video_path = video.path.parent.joinpath(f'{video.path.stem}.chat.mp4')
        video_out = cv2.VideoWriter(
            str(chat_video_path),
            cv2.VideoWriter_fourcc(*'mp4v'),
            fps,
            (video_width, video_height)
        )
        
        # Process frames
        message_index = 0
        
        try:
            while True:
                ret, frame = video_in.read()
                if not ret:
                    break
                
                # Calculate current time
                time_offset = timedelta(milliseconds=video_in.get(cv2.CAP_PROP_POS_MSEC))
                current_time = video.started_at + time_offset
                
                # Ensure timezone consistency for comparisons
                if current_time.tzinfo is not None and current_time.tzinfo.utcoffset(current_time) is not None:
                    # current_time is timezone-aware, make sure we handle naive message timestamps
                    pass  # We'll handle this in the comparison methods
                else:
                    # current_time is naive, make it UTC-aware if needed
                    current_time = current_time.replace(tzinfo=timezone.utc)
                
                # Update message index
                message_index = self._update_message_index(
                    messages, message_index, current_time
                )
                
                # Render chat on frame
                frame_with_chat = self.chat_renderer.render_messages_on_frame(
                    frame, messages, current_time, message_index
                )
                
                # Write frame
                video_out.write(frame_with_chat)
        
        finally:
            video_in.release()
            video_out.release()
        
        # Mux with audio
        return await self._mux_audio(video, trim_path, chat_video_path)
    
    def _update_message_index(
        self,
        messages: List[Message],
        current_index: int,
        current_time
    ) -> int:
        """Update message index to point to the newest message for current time."""
        while current_index < len(messages) - 1:
            message_time = messages[current_index].timestamp
            next_message_time = messages[current_index + 1].timestamp
            
            # Ensure timezone consistency
            if message_time.tzinfo is None:
                message_time = message_time.replace(tzinfo=timezone.utc)
            if next_message_time.tzinfo is None:
                next_message_time = next_message_time.replace(tzinfo=timezone.utc)
            
            if message_time <= current_time:
                if next_message_time > current_time:
                    break
                current_index += 1
            else:
                break
        return current_index
    
    async def _mux_audio(
        self,
        video: VideoFile,
        trim_path: Path,
        chat_video_path: Path
    ) -> Path:
        """Mux the chat video with audio from original."""
        logger.debug('Muxing chat video with audio...')
        
        transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
        chat_stream = ffmpeg.input(str(chat_video_path))
        original_stream = ffmpeg.input(str(trim_path))
        
        output_stream = ffmpeg.output(
            chat_stream['v:0'],
            original_stream['a:0'],
            str(transcode_path),
            vcodec='copy',
            acodec='aac'
        )
        output_stream = ffmpeg.overwrite_output(output_stream)
        ffmpeg.run(output_stream, quiet=True)
        
        # Update video model
        video.transcode_path = transcode_path
        await video.save()
        
        # Clean up chat video
        chat_video_path.unlink()
        
        # Remove original video file (commented out for now)
        # video.path.unlink()
        
        return transcode_path


# Convenience function for backward compatibility
async def generate_chat_video(
    video: VideoFile,
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
    remove_ads: bool = True
) -> Optional[Path]:
    """
    Generate a chat overlay video (backward compatibility function).
    """
    config = ChatVideoConfig(
        width=width,
        height=height,
        x_offset=x_offset,
        y_offset=y_offset,
        padding=padding,
        font_family=font_family,
        font_style=font_style,
        font_size=font_size,
        font_color=font_color,
        background_color=background_color,
        message_duration=message_duration,
        remove_ads=remove_ads
    )
    
    generator = ChatVideoGenerator(config)
    return await generator.generate(video)