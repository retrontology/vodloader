from datetime import datetime
from vodloader.util import *
from vodloader.models import BaseModel, TwitchChannel
from uuid import uuid4


class ClearChatEvent(BaseModel):

    table_name = 'twitch_clearchat'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            user_id INT UNSIGNED NOT NULL,
            timestamp DATETIME NOT NULL,
            duration INT UNSIGNED DEFAULT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """
    
    id: str
    channel: int
    user_id: int
    timestamp: datetime
    duration: int

    def __init__(
            self,
            id: str,
            channel: int,
            user_id: int,
            timestamp: datetime,
            duration: int = None,
        ):
        self.id = id
        self.channel = channel
        self.user_id = user_id
        self.timestamp = timestamp
        self.duration = duration
    
    @classmethod
    def from_event(cls, event):

        tags = parse_tags(event)     

        if 'ban-duration' in tags:
            duration = int(tags['ban-duration'])
        else:
            duration = None

        timestamp = parse_irc_ts(tags['tmi-sent-ts'])

        return cls(
            id = uuid4().__str__(),
            channel = int(tags['room-id']),
            user_id = int(tags['target-user-id']),
            timestamp = timestamp,
            duration = duration
        )
