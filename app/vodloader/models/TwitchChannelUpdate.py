from datetime import datetime
from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel, TwitchChannel


class TwitchChannelUpdate(BaseModel):

    table_name = 'twitch_channel_update'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            timestamp DATETIME NOT NULL,
            title VARCHAR(140) NOT NULL,
            category_name VARCHAR(256) NOT NULL,
            category_id INT UNSIGNED NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """
    
    id: str
    channel: int
    timestamp: datetime
    title: str
    category_name: str
    category_id: int

    def __init__(
            self,
            id: str,
            channel: str|int,
            timestamp: datetime,
            title: str,
            category_name: str,
            category_id: str|int
    ) -> None:
        
        super().__init__()
        self.id = id
        self.channel = int(channel)
        self.timestamp = timestamp
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)
