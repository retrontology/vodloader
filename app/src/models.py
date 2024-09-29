from datetime import datetime, timezone
from pathlib import Path
from typing import Self, List, Dict, Tuple
from .database import *
from enum import Enum
import ffmpeg
import logging
from irc.client import Event

NOT_NULL = 'NOT NULL'

class OrderDirection(Enum):

    ASC = 'ASC'
    DESC = 'DESC'

    def __str__(self) -> str:
        return self.value


class BaseModel(): 
    
    table_name:str = None
    table_command:str = None
    logger: logging.Logger = None
    
    def __init__(self):
        self.logger = logging.getLogger(f'vodloader.models.{type(self).__name__}')

    def _get_extra_attributes(self):
        default_attributes = BaseModel.__dict__
        extra_attributes = []
        for attribute in list(self.__dict__):
            if attribute not in default_attributes:
                extra_attributes.append(attribute)
        return extra_attributes
    
    @classmethod
    async def initialize(cls):
        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(cls.table_command)
        await connection.commit()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

    async def save(self):

        values = []
        attributes = self._get_extra_attributes()
        for attribute in attributes:
            value = self.__getattribute__(attribute)
            match value:
                case Path():
                    value = value.__str__()
                case _:
                     pass
            values.append(value)
        values.extend(values)

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {self.table_name} 
            ({', '.join(attributes)})
            VALUES
            ({', '.join([db.char for x in attributes])})
            {db.duplicate('id')}
            {', '.join([f'{x}={db.char}' for x in attributes])};
            """,
            values
        )
        await connection.commit()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

    @classmethod
    async def get(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
        **kwargs):

        if not kwargs:
            raise RuntimeError('At least one key must be specified to find a model')

        db = await get_db()

        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        where_clause = 'WHERE'
        values = []
        first_iteration = True
        for key in kwargs:

            if not first_iteration:
                where_clause += ' AND'

            if kwargs[key] == None:
                where_clause += f' {key} IS NULL'
            elif kwargs[key] == NOT_NULL:
                where_clause += f' {key} IS NOT NULL'
            else:
                where_clause += f' {key}={db.char}'
                values.append(kwargs[key])

            first_iteration = False

        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {where_clause}
            {order_clause};
            """,
            values
        )
        args = await cursor.fetchone()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args:
            return cls(*args)
        else:
            return None
    
    @classmethod
    async def get_many(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
        **kwargs
    ) -> List[Self]:
        db = await get_db()

        if not kwargs:
            raise RuntimeError('At least one key must be specified to find models')

        where_clause = 'WHERE'
        values = []
        for key in kwargs:
            if kwargs[key] == None:
                where_clause += f' {key} IS NULL'
            if kwargs[key] == NOT_NULL:
                where_clause += f' {key} IS NOT NULL'
            else:
                where_clause += f' {key}={db.char}'
                values.append(kwargs[key])
        
        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {where_clause}
            {order_clause};
            """,
            values
        )
        args_list = await cursor.fetchall()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args_list:
            return (cls(*args) for args in args_list)
        else:
            return None

    @classmethod
    async def all(
        cls,
        order_by: str = None,
        order: OrderDirection = OrderDirection.ASC,
    ):
        if order_by:
            order_clause = f'ORDER BY {order_by} {order}'
        else:
            order_clause = ''

        db = await get_db()
        connection = await db.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {cls.table_name}
            {order_clause};
            """
        )
        args_list = await cursor.fetchall()
        await cursor.close()
        closer = connection.close()
        if closer: await closer

        if args_list:
            return (cls(*args) for args in args_list)
        else:
            return None

class EndableModel(BaseModel):

    async def end(self, end: datetime = None):

        if end == None:
            end = datetime.now(timezone.utc)
        
        self.ended_at = end
        await self.save()


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
            badge_info VARCHAR(64) DEFAULT NULL,
            badges VARCHAR(64) DEFAULT NULL,
            color VARCHAR(7) DEFAULT NULL,
            emotes VARCHAR(64) DEFAULT NULL,
            first_message BOOL NOT NULL DEFAULT 0,
            flags VARCHAR(32) DEFAULT NULL,
            mod BOOL NOT NULL DEFAULT 0,
            returning_chatter BOOL NOT NULL DEFAULT 0,
            subscriber BOOL NOT NULL DEFAULT 0,
            timestamp DATETIME NOT NULL,
            turbo BOOL NOT NULL DEFAULT 0,
            user_id INT UNSIGNED NOT NULL,
            user_type VARCHAR(32) DEFAULT NULL,
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
    mod: bool
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
            channel: str,
            display_name: str,
            badge_info: str,
            badges: str,
            color: str,
            emotes: str,
            first_message: bool,
            flags: str,
            mod: bool,
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
        self.mod = mod
        self.returning_chatter = returning_chatter
        self.subscriber = subscriber
        self.timestamp = timestamp
        self.turbo = turbo
        self.user_id = user_id
        self.user_type = user_type


    @classmethod
    def from_event(cls, event: Event) -> Self:
        
        tags = {}
        for tag in event.tags:
            tags[tag['key']] = tag['value']

        return cls(
            id = tags['id'],
            content = event.arguments[0],
            channel = event.target[1:],
            display_name = tags['display-name'],
            badge_info = tags['badge-info'],
            badges = tags['badges'],
            color = tags['color'],
            emotes = tags['emotes'],
            first_message = tags['first-msg'] == '1',
            flags = tags['flags'],
            mod = tags['mod'] == '1',
            returning_chatter = tags['returning-chatter'] == '1',
            #room_id = int(tags['room-id']),
            subscriber = tags['subscriber'] == '1',
            timestamp = datetime.fromtimestamp(float(tags['tmi-sent-ts'])/1000),
            turbo = tags['turbo'] == '1',
            user_id = int(tags['user-id']),
            user_type = tags['user-type'],
        )
    
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
    Message
]


async def initialize_models():
    for model in MODELS:
        await model.initialize()
