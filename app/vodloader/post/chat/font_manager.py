"""
Font management for chat rendering.
"""

import logging
from typing import List
from PIL import ImageFont
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font

logger = logging.getLogger('vodloader.chat_video.font_manager')


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