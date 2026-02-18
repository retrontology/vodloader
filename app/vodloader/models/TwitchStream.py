from datetime import datetime
from typing import Self, List
from vodloader.database import *
from vodloader.util import *
from vodloader.models import EndableModel, TwitchChannel


class TwitchStream(EndableModel):

    table_name = 'twitch_stream'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGINT UNSIGNED NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            title VARCHAR(140) NOT NULL,
            category_name VARCHAR(256) NOT NULL,
            category_id INT UNSIGNED NOT NULL,
            started_at DATETIME NOT NULL,
            ended_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """
    
    id: int
    channel: int
    title: str
    category_name: str
    category_id: int
    started_at: datetime
    ended_at: datetime

    def __init__(
            self,
            id: str|int,
            channel: str|int,
            title: str,
            category_name: str,
            category_id: str|int,
            started_at: datetime,
            ended_at: datetime = None,
    ) -> None:
        
        super().__init__()
        self.id = int(id)
        self.channel = int(channel)
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)
        self.started_at = started_at
        self.ended_at = ended_at
