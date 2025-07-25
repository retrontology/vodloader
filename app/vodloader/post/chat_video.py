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
        self.start_x = 20
        self.start_y = 20
    
    def setup_dimensions(self, video_width: int, video_height: int) -> Tuple[int, int, int]:
        """Calculate chat dimensions based on video properties."""
        chat_width = self.config.width
        chat_height = self.config.height if self.config.height else video_height
        max_y = chat_height - (self.start_y * 2)
        return chat_width, chat_height, max_y
    
    def render_messages_on_frame(
        self,
        frame: np.ndarray,
        messages: List[Message],
        current_time: timedelta,
        message_index: int,
        chat_width: int,
        max_y: int
    ) -> np.ndarray:
        """Render chat messages on a single frame."""
        base_image = Image.fromarray(frame, mode="RGB")
        draw = ImageDraw.Draw(base_image)
        
        # Iterate through visible messages
        current_y = self.start_y
        visible_message_index = message_index
        
        while visible_message_index >= 0 and current_y <= max_y:
            message = messages[visible_message_index]
            
            # Check if message is still visible
            message_time = message.timestamp
            if message_time.tzinfo is None:
                # Make naive timestamp timezone-aware to match current_time
                message_time = message_time.replace(tzinfo=timezone.utc)
            
            if (current_time - message_time) > self.config.message_duration:
                break
            
            # Render this message
            lines_rendered = self._render_message(
                draw, message, current_y, chat_width, max_y
            )
            
            if lines_rendered == 0:
                # Message too big to fit, stop rendering
                break
            
            current_y += lines_rendered * self.line_height
            visible_message_index -= 1
        
        return np.array(base_image)
    
    def _render_message(
        self,
        draw: ImageDraw.Draw,
        message: Message,
        start_y: int,
        chat_width: int,
        max_y: int
    ) -> int:
        """
        Render a single message and return number of lines rendered.
        Returns 0 if message couldn't fit.
        """
        prefix = f'{message.display_name}:'
        
        # Break the message into lines
        words = message.content.split(' ')
        lines = [[]]
        temp_x = self.start_x + draw.textlength(prefix, font=self.font)
        
        for word in words:
            word_length = draw.textlength(f' {word}', font=self.font)
            if temp_x + word_length > chat_width:
                lines.append([word])
                temp_x = self.start_x + draw.textlength(word, font=self.font)
            else:
                lines[-1].append(word)
                temp_x += word_length
        
        # Check if message fits
        total_height = len(lines) * self.line_height
        if start_y + total_height > max_y:
            return 0
        
        # Draw the message
        current_y = start_y
        draw.text(
            (self.start_x, current_y),
            prefix,
            font=self.font,
            fill=message.color,
            stroke_fill=self.config.background_color,
            stroke_width=2
        )
        
        current_x = self.start_x + draw.textlength(f'{prefix} ', font=self.font)
        
        for line in lines:
            if not line:
                continue
            line_text = ' '.join(line)
            draw.text(
                (current_x, current_y),
                line_text,
                font=self.font,
                fill=self.config.font_color,
                stroke_fill=self.config.background_color,
                stroke_width=2
            )
            current_y += self.line_height
            current_x = self.start_x
        
        return len(lines)


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
        
        # Setup chat dimensions
        chat_width, chat_height, max_y = self.chat_renderer.setup_dimensions(
            video_width, video_height
        )
        
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
                    frame, messages, current_time, message_index, chat_width, max_y
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