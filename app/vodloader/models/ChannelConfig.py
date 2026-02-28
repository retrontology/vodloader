from vodloader.models import BaseModel
from typing import Self, Optional


class ChannelConfig(BaseModel):
    DEFAULT_CHAT_FONT_FAMILY = "Roboto Mono"
    DEFAULT_CHAT_FONT_SIZE = 14
    DEFAULT_CHAT_FONT_STYLE = "normal"
    DEFAULT_CHAT_FONT_WEIGHT = "normal"
    DEFAULT_CHAT_TEXT_COLOR = "#ffffff"
    DEFAULT_CHAT_TEXT_SHADOW_COLOR = "#000000"
    DEFAULT_CHAT_TEXT_SHADOW_SIZE = 1
    DEFAULT_CHAT_POSITION = "top-left"
    DEFAULT_CHAT_PADDING = 20
    DEFAULT_CHAT_MESSAGE_DURATION = 30.0
    DEFAULT_KEEP_CHAT_OVERLAY = True

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
    
    # Chat overlay fields
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
        self.chat_font_family = chat_font_family if chat_font_family is not None else self.DEFAULT_CHAT_FONT_FAMILY
        self.chat_font_size = chat_font_size if chat_font_size is not None else self.DEFAULT_CHAT_FONT_SIZE
        self.chat_font_style = chat_font_style if chat_font_style is not None else self.DEFAULT_CHAT_FONT_STYLE
        self.chat_font_weight = chat_font_weight if chat_font_weight is not None else self.DEFAULT_CHAT_FONT_WEIGHT
        self.chat_text_color = chat_text_color if chat_text_color is not None else self.DEFAULT_CHAT_TEXT_COLOR
        self.chat_text_shadow_color = (
            chat_text_shadow_color if chat_text_shadow_color is not None else self.DEFAULT_CHAT_TEXT_SHADOW_COLOR
        )
        self.chat_text_shadow_size = (
            chat_text_shadow_size if chat_text_shadow_size is not None else self.DEFAULT_CHAT_TEXT_SHADOW_SIZE
        )
        self.chat_overlay_width = chat_overlay_width
        self.chat_overlay_height = chat_overlay_height
        self.chat_position = chat_position if chat_position is not None else self.DEFAULT_CHAT_POSITION
        self.chat_padding = chat_padding if chat_padding is not None else self.DEFAULT_CHAT_PADDING
        self.chat_message_duration = (
            chat_message_duration if chat_message_duration is not None else self.DEFAULT_CHAT_MESSAGE_DURATION
        )
        self.keep_chat_overlay = (
            keep_chat_overlay if keep_chat_overlay is not None else self.DEFAULT_KEEP_CHAT_OVERLAY
        )

    # Configuration getter methods with default value fallbacks
    def get_chat_font_family(self) -> str:
        """Get chat font family."""
        return self.chat_font_family
    
    def get_chat_font_size(self) -> int:
        """Get chat font size."""
        return self.chat_font_size
    
    def get_chat_font_style(self) -> str:
        """Get chat font style."""
        return self.chat_font_style
    
    def get_chat_font_weight(self) -> str:
        """Get chat font weight."""
        return self.chat_font_weight
    
    def get_chat_text_color(self) -> str:
        """Get chat text color."""
        return self.chat_text_color
    
    def get_chat_text_shadow_color(self) -> str:
        """Get chat text shadow color."""
        return self.chat_text_shadow_color
    
    def get_chat_text_shadow_size(self) -> int:
        """Get chat text shadow size."""
        return self.chat_text_shadow_size
    
    def get_chat_overlay_width(self) -> Optional[int]:
        """Get chat overlay width (None means calculate from stream dimensions)"""
        return self.chat_overlay_width
    
    def get_chat_overlay_height(self) -> Optional[int]:
        """Get chat overlay height (None means calculate from stream dimensions)"""
        return self.chat_overlay_height
    
    def get_chat_position(self) -> str:
        """Get chat position for video compositor."""
        return self.chat_position
    
    def get_chat_padding(self) -> int:
        """Get chat padding for video compositor."""
        return self.chat_padding
    

    
    def get_chat_message_duration(self) -> float:
        """Get chat message duration."""
        return self.chat_message_duration
    
    def get_keep_chat_overlay(self) -> bool:
        """Get keep chat overlay setting."""
        return self.keep_chat_overlay