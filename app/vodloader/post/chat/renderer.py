"""
Chat message rendering on video frames.
"""

import numpy as np
from PIL import Image, ImageDraw
from datetime import timedelta, timezone
from typing import List

from vodloader.models import Message
from .config import ChatVideoConfig
from .font_manager import FontManager
from .area import ChatArea


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
        self._message_cache = {}  # Cache for pre-computed message layouts
    
    def setup_chat_area(self, video_width: int, video_height: int) -> ChatArea:
        """Setup the chat area for the given video dimensions."""
        self.chat_area = ChatArea(self.config, video_width, video_height)
        
        import logging
        logger = logging.getLogger('vodloader.chat_video.renderer')
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
                # For truncated messages, don't show prefix (it would be misleading)
                # For complete messages, show prefix on the first line
                if is_truncated:
                    show_prefix = False  # No prefix for truncated messages
                else:
                    show_prefix = (i == 0)  # First line of the complete message
                
                self._draw_message_line(draw, message, lines_to_render[i], current_y, show_prefix)
                lines_used += 1
        
        return np.array(base_image)
    
    def _wrap_message(self, draw: ImageDraw.Draw, message: Message) -> List[str]:
        """Wrap message text into lines that fit the chat width (with caching)."""
        # Check cache first
        cache_key = (message.id, self.chat_area.content_width)
        if cache_key in self._message_cache:
            return self._message_cache[cache_key]
        
        prefix = f'{message.display_name}: '
        content = message.content.strip()
        
        # Handle empty content
        if not content:
            result = ['']
            self._message_cache[cache_key] = result
            return result
        
        # Calculate available widths
        prefix_width = draw.textlength(prefix, font=self.font)
        first_line_width = self.chat_area.content_width - prefix_width
        full_line_width = self.chat_area.content_width
        
        words = content.split()  # split() handles multiple spaces better than split(' ')
        lines = []
        current_line = []
        is_first_line = True
        
        for word in words:
            # Skip empty words (shouldn't happen with split() but safety first)
            if not word:
                continue
            
            # Check if this single word is too long for any line
            word_width = draw.textlength(word, font=self.font)
            available_width = first_line_width if is_first_line else full_line_width
            
            if word_width > available_width:
                # Single word is too long - put it on its own line anyway
                # (Better to overflow than to break the word)
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                    is_first_line = False
                lines.append(word)
                is_first_line = False
                continue
            
            # Calculate what the line would look like with this word added
            test_line = current_line + [word]
            test_text = ' '.join(test_line)
            test_width = draw.textlength(test_text, font=self.font)
            
            if test_width <= available_width:
                # Word fits on current line
                current_line.append(word)
            else:
                # Word doesn't fit, start new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                is_first_line = False
        
        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))
        
        result = lines if lines else ['']
        self._message_cache[cache_key] = result
        return result
    
    def _draw_message_line(self, draw: ImageDraw.Draw, message: Message, line: str, y: int, is_first_line: bool):
        """Draw a single line of a message."""
        if is_first_line:
            # Draw prefix + first line
            prefix = f'{message.display_name}: '
            draw.text(
                (self.chat_area.content_x, y),
                prefix,
                font=self.font,
                fill=message.color if message.color else '#ffffff',
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