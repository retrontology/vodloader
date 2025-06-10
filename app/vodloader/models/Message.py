from datetime import datetime
from typing import Self, List, Dict, Tuple
from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel, TwitchChannel, VideoFile
from irc.client import Event


class Message(BaseModel):

    table_name = 'twitch_message'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            content VARCHAR(500) DEFAULT NULL,
            channel INT UNSIGNED NOT NULL,
            display_name VARCHAR(25) NOT NULL,
            badge_info VARCHAR(256) DEFAULT NULL,
            badges VARCHAR(256) DEFAULT NULL,
            color VARCHAR(7) DEFAULT NULL,
            emotes VARCHAR(256) DEFAULT NULL,
            first_message BOOL NOT NULL DEFAULT 0,
            flags VARCHAR(256) DEFAULT NULL,
            moderator BOOL NOT NULL DEFAULT 0,
            returning_chatter BOOL NOT NULL DEFAULT 0,
            subscriber BOOL NOT NULL DEFAULT 0,
            timestamp DATETIME NOT NULL,
            turbo BOOL NOT NULL DEFAULT 0,
            user_id INT UNSIGNED NOT NULL,
            user_type VARCHAR(256) DEFAULT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """

    id: str
    content: str
    channel: int
    display_name: str
    badge_info: str
    badges: str
    color: str
    emotes: str
    first_message: bool
    flags: str
    moderator: bool
    returning_chatter: bool
    subscriber: bool
    timestamp: datetime
    turbo: bool
    user_id: int
    user_type: str
    
    def __init__(
            self,
            id: str,
            content: str,
            channel: int,
            display_name: str,
            badge_info: str,
            badges: str,
            color: str,
            emotes: str,
            first_message: bool,
            flags: str,
            moderator: bool,
            returning_chatter: bool,
            subscriber: bool,
            timestamp: datetime,
            turbo: bool,
            user_id: int,
            user_type: str,
        ) -> None:
        self.id = id
        self.content = content
        self.channel = channel
        self.display_name = display_name
        self.badge_info = badge_info
        self.badges = badges
        self.color = color
        self.emotes = emotes
        self.first_message = first_message
        self.flags = flags
        self.moderator = moderator
        self.returning_chatter = returning_chatter
        self.subscriber = subscriber
        self.timestamp = timestamp
        self.turbo = turbo
        self.user_id = user_id
        self.user_type = user_type


    @classmethod
    def from_event(cls, event: Event) -> Self:
        
        tags = parse_tags(event)

        timestamp = parse_irc_ts(tags['tmi-sent-ts'])

        return cls(
            id = tags['id'],
            content = event.arguments[0],
            channel = int(tags['room-id']),
            display_name = tags['display-name'],
            badge_info = tags['badge-info'],
            badges = tags['badges'],
            color = tags['color'],
            emotes = tags['emotes'],
            first_message = 'first-msg' in tags and tags['first-msg'] == '1',
            flags = tags['flags'],
            moderator = tags['mod'] == '1',
            returning_chatter = tags['returning-chatter'] == '1',
            subscriber = tags['subscriber'] == '1',
            timestamp = timestamp,
            turbo = tags['turbo'] == '1',
            user_id = int(tags['user-id']),
            user_type = tags['user-type'],
        )
    
    @classmethod
    async def for_video(cls, video: VideoFile) -> List[Self]:

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT {cls.table_name}.*
            FROM {cls.table_name},
             (SELECT started_at, ended_at, channel
             FROM {video.table_name}
             WHERE id = {db.char}) AS stream
            WHERE {cls.table_name}.timestamp BETWEEN stream.started_at and stream.ended_at
            AND {cls.table_name}.channel = stream.channel
            ORDER BY timestamp ASC;
            """,
            (video.id, )
        )
        args_list = await cursor.fetchall()
        messages = [cls(*args) for args in args_list]
        await cursor.close()
        closer = connection.close()
        if closer: await closer
        return messages
    
    def parse_badges(self) -> List[str] | None:
        if self.badges == None:
            return None
        return self.badges.split(',')

    def parse_badge_info(self) -> Dict[str, str]:
        if self.badge_info == None:
            return None
        
        badge_info = {}
        for info in value.split(','):
            key, value = info.split('/', 1)
            badge_info[key] = value
        return badge_info
    
    def parse_emotes(self) -> Dict[int, List[Tuple[int, int]]]:
        if self.emotes == None:
            return None
        
        emotes = {}
        for emote in self.emotes.split('/'):
            number, places= emote.split(':', 1)
            index = []
            for place in places.split(','):
                start, end = place.split('-', 1)
                index.append((int(start), int(end)))
            emotes[int(number)] = index.copy()
        return emotes
