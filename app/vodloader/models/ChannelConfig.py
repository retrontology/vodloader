from vodloader.models import BaseModel
from typing import Self


class ChannelConfig(BaseModel):

    table_name = 'channel_config'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT UNSIGNED NOT NULL UNIQUE,
            quality VARCHAR(8) NOT NULL DEFAULT 'best',
            delete_original_video BOOL NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (id) REFERENCES twitch_channel(id) ON DELETE CASCADE
        );
        """

    id: int
    quality: str
    delete_original_video: bool

    def __init__(
        self,
        id: int,
        quality: str = 'best',
        delete_original_video: bool = False,
    ) -> None:
        super().__init__()
        self.id = id
        self.quality = quality
        self.delete_original_video = delete_original_video

    