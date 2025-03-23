from datetime import datetime
from vodloader.util import *
from vodloader.models import BaseModel, TwitchChannel, Message
from uuid import uuid4


class ClearMsgEvent(BaseModel):

    table_name = 'twitch_clearmsg'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            message_id VARCHAR(36) NOT NULL,
            timestamp DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id),
            FOREIGN KEY (message_id) REFERENCES {Message.table_name}(id) ON DELETE CASCADE
        );
        """
    
    id: str
    channel: int
    message_id: str
    timestamp: datetime

    def __init__(
            self,
            id: str,
            channel: int,
            message_id: int,
            timestamp: datetime,
        ):
        self.id = id
        self.channel = channel
        self.message_id = message_id
        self.timestamp = timestamp
    
    @classmethod
    def from_event(cls, event: Event):

        tags = parse_tags(event)     

        timestamp = parse_irc_ts(tags['tmi-sent-ts'])

        return cls(
            id = uuid4().__str__(),
            channel = int(tags['room-id']),
            message_id = tags['target-msg-id'],
            timestamp = timestamp,
        )
