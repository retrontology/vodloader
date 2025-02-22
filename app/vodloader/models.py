from datetime import datetime, timezone
from pathlib import Path
from typing import Self, List, Dict, Tuple
from .database import *
from .util import *
from enum import Enum
import ffmpeg
import logging
from irc.client import Event
from uuid import uuid4
import time


class TwitchChannel(BaseModel):

    table_name = 'twitch_channel'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT UNSIGNED NOT NULL UNIQUE,
            login VARCHAR(25) NOT NULL UNIQUE,
            name VARCHAR(25) NOT NULL UNIQUE,
            active BOOL NOT NULL DEFAULT 0,
            quality VARCHAR(8),
            PRIMARY KEY (id)
        );
        """

    id: int
    login: str
    name: str
    active: bool
    quality: str

    def __init__(
            self,
            id: str|int,
            login: str,
            name: str,
            active: bool = True,
            quality: str = 'best',
        ) -> None:

        super().__init__()
        self.id = int(id)
        self.login = login
        self.name = name
        self.active = active
        self.quality = quality

    async def activate(self):
        self.active = True
        await self.save()
    
    async def deactivate(self):
        self.active = False
        await self.save()


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
    

    async def get_messages(self) -> List[Self]:
        messages = await Message.from_stream(self.id)
        return messages


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


class VideoFile(EndableModel):

    table_name = 'video_file'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            stream BIGINT UNSIGNED NOT NULL,
            channel INT UNSIGNED NOT NULL,
            quality VARCHAR(8),
            path VARCHAR(4096),
            started_at DATETIME NOT NULL,
            ended_at DATETIME DEFAULT NULL,
            transcode_path VARCHAR(4096) DEFAULT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (stream) REFERENCES {TwitchStream.table_name}(id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """

    id: str
    stream: int
    channel: int
    quality: int
    path: Path
    started_at: datetime
    ended_at: datetime
    transcode_path: Path
    

    def __init__(
            self,
            id: str,
            stream: str|int,
            channel: str|int,
            quality: str,
            path: str|Path,
            started_at: datetime,
            ended_at: datetime = None,
            transcode_path: str|Path = None,
    ) -> None:
        
        super().__init__()
        self.id = id
        self.stream = int(stream)
        self.channel = int(channel)
        self.quality = quality
        self.path = Path(path).resolve()
        self.started_at = started_at
        self.ended_at = ended_at
        self.transcode_path = Path(transcode_path).resolve() if transcode_path else None

    @classmethod
    async def get_nontranscoded(cls) -> List[Self]:
        results = await cls.get_many(
            transcode_path=None,
            order_by='started_at',
            order=OrderDirection.ASC
        )
        return results

    @classmethod
    async def get_next_transcode(cls) -> Self:
        next = await cls.get(
            transcode_path=None,
            ended_at=NOT_NULL,
            order_by='started_at',
            order=OrderDirection.ASC
        )
        return next
    
    async def remove_original(self):
        
        if not self.path:
            raise VideoAlreadyRemoved
        
        path = self.path
        self.path.unlink()
        self.path = None
        await self.save()
        self.logger.info(f'The original stream file at {path.__str__()} has been deleted')
    
    async def transcode(self):

        if not self.ended_at:
            raise VideoFileNotEnded
        
        if self.transcode_path:
            raise VideoAlreadyTranscoded
        
        self.logger.info(f'Transcoding {self.path}')
        loop = asyncio.get_event_loop()
        self.transcode_path = await loop.run_in_executor(None, self._transcode)
        await self.save()
        self.logger.info(f'Finished transcoding {self.path} to {self.transcode_path}')
        await self.remove_original()
        

    def _transcode(self) -> Path:
        transcode_path = self.path.parent.joinpath(f'{self.path.stem}.mp4')
        stream = ffmpeg.input(self.path.__str__())
        stream = ffmpeg.output(stream, transcode_path.__str__(), vcodec='copy')
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream, quiet=True)
        return transcode_path


class YoutubeVideo(BaseModel):

    table_name = 'youtube_video'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(12) NOT NULL UNIQUE,
            video VARCHAR(36) NOT NULL UNIQUE,
            uploaded BOOL NOT NULL DEFAULT 0,
            PRIMARY KEY (id),
            FOREIGN KEY (video) REFERENCES {VideoFile.table_name}(id)
        );
        """

    id: str
    video: str
    uploaded: bool
    
    def __init__(
            self,
            id: str,
            video: str,
            uploaded: bool = False,
    ) -> None:
        
        super().__init__()
        self.id = id
        self.video = video
        self.uploaded = uploaded
    
    async def set_uploaded(self, uploaded: bool = True):
        self.uploaded = uploaded
        await self.save()


class TwitchClient(BaseModel):

    table_name = 'twitch_client'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            client_id VARCHAR(30) NOT NULL,
            client_secret VARCHAR(30) NOT NULL,
            PRIMARY KEY (id)
        );
        """

    id: int
    client_id: str
    client_secret: str

    def __init__(
            self,
            id: int|str,
            client_id: str,
            client_secret: str
    ) -> None:
        
        super().__init__()
        self.id = int(id)
        self.client_id = client_id
        self.client_secret = client_secret
    
    @classmethod
    async def set_client(cls, client_id:str, client_secret:str) -> None:
        client = cls(0, client_id, client_secret)
        await client.save()
    
    @classmethod
    async def get_client(self) -> tuple[str, str]|None:
        client = await self.get(id=0)
        if client:
            return (client.client_id, client.client_secret)
        else:
            return None


class TwitchAuth(BaseModel):

    table_name = 'twitch_auth'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            auth_token VARCHAR(30) DEFAULT NULL,
            refresh_token VARCHAR(50) DEFAULT NULL,
            PRIMARY KEY (id)
        );
        """

    id: int
    auth_token: str
    refresh_token: str

    def __init__(
            self,
            id: int|str,
            auth_token: str,
            refresh_token: str
    ) -> None:
        
        super().__init__()
        self.id = int(id)
        self.auth_token = auth_token
        self.refresh_token = refresh_token

    @classmethod
    async def set_auth(cls, auth_token:str, refresh_token:str) -> None:
        client = cls(0, auth_token, refresh_token)
        await client.save()
    
    @classmethod
    async def get_auth(self) -> tuple[str, str]|None:
        client = await self.get(id=0)
        if client:
            return (client.auth_token, client.refresh_token)
        else:
            return None


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
    async def from_stream(cls, stream_id: int) -> List[Self]:

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT {cls.table_name}.*
            FROM {cls.table_name},
             (SELECT started_at, ended_at, channel
             FROM {TwitchStream.table_name}
             WHERE id = {db.char}) AS stream
            WHERE {cls.table_name}.timestamp BETWEEN stream.started_at and stream.ended_at
            AND {cls.table_name}.channel = stream.channel
            ORDER BY timestamp ASC;
            """,
            (stream_id, )
        )
        args_list = await cursor.fetchall()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args_list:
            return list(cls(*args) for args in args_list)
        else:
            return None
    
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
    def from_event(cls, event: Event):

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


class VideoFileNotEnded(Exception): pass
class VideoAlreadyTranscoded(Exception): pass
class VideoAlreadyRemoved(Exception): pass


MODELS: List[BaseModel] = [
    TwitchChannel,
    TwitchStream,
    TwitchChannelUpdate,
    VideoFile,
    YoutubeVideo,
    TwitchClient,
    TwitchAuth,
    Message,
    ClearChatEvent,
    ClearMsgEvent,
]


async def initialize_models():
    for model in MODELS:
        await model.initialize()
