from vodloader.models import BaseModel
from typing import Self, Optional


class ChannelConfig(BaseModel):

    table_name = 'channel_config'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT UNSIGNED NOT NULL UNIQUE,
            quality VARCHAR(8) NOT NULL DEFAULT 'best',
            delete_original_video BOOL NOT NULL,
            chat_font_family VARCHAR(100) DEFAULT NULL,
            chat_font_size INT DEFAULT NULL,
            chat_font_style VARCHAR(20) DEFAULT NULL,
            chat_font_weight VARCHAR(20) DEFAULT NULL,
            chat_text_color VARCHAR(7) DEFAULT NULL,
            chat_text_shadow_color VARCHAR(7) DEFAULT NULL,
            chat_text_shadow_size INT DEFAULT NULL,
            chat_overlay_width INT DEFAULT NULL,
            chat_overlay_height INT DEFAULT NULL,
            chat_position VARCHAR(20) DEFAULT NULL,
            chat_padding INT DEFAULT NULL,
            chat_message_duration FLOAT DEFAULT NULL,
            keep_chat_overlay BOOL DEFAULT TRUE,
            PRIMARY KEY (id),
            FOREIGN KEY (id) REFERENCES twitch_channel(id) ON DELETE CASCADE
        );
        """

    id: int
    quality: str
    delete_original_video: bool
    
    # Chat overlay fields (all nullable for backward compatibility)
    chat_font_family: Optional[str]
    chat_font_size: Optional[int]
    chat_font_style: Optional[str]
    chat_font_weight: Optional[str]
    chat_text_color: Optional[str]
    chat_text_shadow_color: Optional[str]
    chat_text_shadow_size: Optional[int]
    chat_overlay_width: Optional[int]
    chat_overlay_height: Optional[int]
    chat_position: Optional[str]
    chat_padding: Optional[int]
    chat_message_duration: Optional[float]
    keep_chat_overlay: Optional[bool]

    def __init__(
        self,
        id: int,
        quality: str = 'best',
        delete_original_video: bool = False,
        chat_font_family: Optional[str] = None,
        chat_font_size: Optional[int] = None,
        chat_font_style: Optional[str] = None,
        chat_font_weight: Optional[str] = None,
        chat_text_color: Optional[str] = None,
        chat_text_shadow_color: Optional[str] = None,
        chat_text_shadow_size: Optional[int] = None,
        chat_overlay_width: Optional[int] = None,
        chat_overlay_height: Optional[int] = None,
        chat_position: Optional[str] = None,
        chat_padding: Optional[int] = None,
        chat_message_duration: Optional[float] = None,
        keep_chat_overlay: Optional[bool] = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.quality = quality
        self.delete_original_video = delete_original_video
        self.chat_font_family = chat_font_family
        self.chat_font_size = chat_font_size
        self.chat_font_style = chat_font_style
        self.chat_font_weight = chat_font_weight
        self.chat_text_color = chat_text_color
        self.chat_text_shadow_color = chat_text_shadow_color
        self.chat_text_shadow_size = chat_text_shadow_size
        self.chat_overlay_width = chat_overlay_width
        self.chat_overlay_height = chat_overlay_height
        self.chat_position = chat_position
        self.chat_padding = chat_padding
        self.chat_message_duration = chat_message_duration
        self.keep_chat_overlay = keep_chat_overlay

    # Configuration getter methods with default value fallbacks
    def get_chat_font_family(self) -> str:
        """Get chat font family with default fallback to Roboto Mono"""
        return self.chat_font_family or "Roboto Mono"
    
    def get_chat_font_size(self) -> int:
        """Get chat font size with default fallback to 14"""
        return self.chat_font_size or 14
    
    def get_chat_font_style(self) -> str:
        """Get chat font style with default fallback to normal"""
        return self.chat_font_style or "normal"
    
    def get_chat_font_weight(self) -> str:
        """Get chat font weight with default fallback to normal"""
        return self.chat_font_weight or "normal"
    
    def get_chat_text_color(self) -> str:
        """Get chat text color with default fallback to white"""
        return self.chat_text_color or "#ffffff"
    
    def get_chat_text_shadow_color(self) -> str:
        """Get chat text shadow color with default fallback to black"""
        return self.chat_text_shadow_color or "#000000"
    
    def get_chat_text_shadow_size(self) -> int:
        """Get chat text shadow size with default fallback to 1"""
        return self.chat_text_shadow_size or 1
    
    def get_chat_overlay_width(self) -> Optional[int]:
        """Get chat overlay width (None means calculate from video dimensions)"""
        return self.chat_overlay_width
    
    def get_chat_overlay_height(self) -> Optional[int]:
        """Get chat overlay height (None means calculate from video dimensions)"""
        return self.chat_overlay_height
    
    def get_chat_position(self) -> str:
        """Get chat position with default fallback to top-right"""
        return self.chat_position or "top-right"
    
    def get_chat_padding(self) -> int:
        """Get chat padding with default fallback to 20"""
        return self.chat_padding or 20
    
    def get_chat_message_duration(self) -> float:
        """Get chat message duration with default fallback to 30.0 seconds"""
        return self.chat_message_duration or 30.0
    
    def get_keep_chat_overlay(self) -> bool:
        """Get keep chat overlay setting with default fallback to True"""
        return self.keep_chat_overlay if self.keep_chat_overlay is not None else True