import aiosqlite
import aiomysql
from pathlib import Path
from datetime import datetime
from datetime import datetime
from uuid import uuid4
import asyncio
from .models import *
from aiosqlite import Connection as SQLiteConnection
from aiomysql import Connection as MySQLConnection
import os

CLIENT_NUM = 0
DEFAULT_TYPE = 'sqlite'
DEFAULT_PATH = 'db.sqlite'

class BaseDatabase():

    char = None

    def __init__(self) -> None:
        pass

    @classmethod
    async def create(cls, *args, **kwargs):
        database = cls(*args, **kwargs)
        await database.connect()
        await database.initialize()
        return database

    async def connect(self) -> SQLiteConnection|MySQLConnection:
        pass

    def duplicate(self, column:str):
        return 'ON DUPLICATE KEY UPDATE'

    async def initialize(self) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()

        for model in MODELS:
            await cursor.execute(model.table_command)
            await connection.commit()
        
        await cursor.close()
        await connection.close()

    # Low level functions

    async def add_twitch_channel(self, channel: TwitchChannel) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {TwitchChannel.table_name} 
            (id, login, name, active, quality)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char})
            {self.duplicate('id')}
            active={self.char}, quality={self.char};
            """,
            (channel.id, channel.login, channel.name, channel.active, channel.quality, channel.active, channel.quality)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()

    async def activate_twitch_channel(self, channel: TwitchChannel) -> TwitchChannel:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            UPDATE {TwitchChannel.table_name}
            SET active = {self.char}
            WHERE id = {self.char};
            """,
            (True, channel.id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        channel.active = True
        return channel

    async def deactivate_twitch_channel(self, channel: TwitchChannel) -> TwitchChannel:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            UPDATE {TwitchChannel.table_name}
            SET active = {self.char}
            WHERE id = {self.char};
            """,
            (False, channel.id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        channel.active = False
        return channel

    async def get_twitch_channel(
            self,
            id: str|int|None = None,
            login: str|None = None,
            name: str|None = None,
        ) -> TwitchChannel | None:

        if id == login == name == None:
            raise Exception('One of "id", "login", or "name" must be specified')
        i = iter([id, login, name])
        if not (any(i) and not any(i)):
            raise Exception('Only one of "id", "login", or "name" must be specified')
        
        connection = await self.connect()
        cursor = await connection.cursor()
        if id:
            await cursor.execute(
                f"""
                SELECT * FROM {TwitchChannel.table_name}
                WHERE id = {self.char};
                """,
                (id,)
            )
        elif login:
            await cursor.execute(
                f"""
                SELECT * FROM {TwitchChannel.table_name}
                WHERE login = {self.char};
                """,
                (login,)
            )
        elif name:
            await cursor.execute(
                f"""
                SELECT * FROM {TwitchChannel.table_name}
                WHERE name = {self.char};
                """,
                (name,)
            )
        args = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        if args:
            return TwitchChannel(*args)
        else:
            return None

    async def get_twitch_channels(self) -> List[TwitchChannel]:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {TwitchChannel.table_name};
            """
        )
        channels_args = await cursor.fetchall()
        await cursor.close()
        await connection.close()
        channels = []
        for channel_args in channels_args:
            channels.append(TwitchChannel(*channel_args))
        return channels

    async def add_twitch_stream(self, stream: TwitchStream) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {TwitchStream.table_name}
            (id, channel, title, category_name, category_id, started_at, ended_at)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (stream.id, stream.channel, stream.title, stream.category_name, stream.category_id, stream.started_at, stream.ended_at)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
    
    async def end_twitch_stream(self, stream: TwitchStream, ended_at: datetime) -> TwitchStream:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            UPDATE {TwitchStream.table_name}
            SET ended_at = {self.char}
            WHERE id = {self.char};
            """,
            (ended_at, stream.id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        stream.ended_at = ended_at
        return stream
    
    async def get_twitch_stream(self, id:str|int) -> TwitchStream | None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {TwitchStream.table_name}
            WHERE id = {self.char}
            """,
            (id,)
        )
        args = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        if args:
            return TwitchStream(*args)
        else:
            return None

    async def add_twitch_update(self, update: TwitchChannelUpdate) -> None:
        connection = await self.connect()
        update_id = uuid4().__str__()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {TwitchChannelUpdate.table_name}
            (id, channel, timestamp, title, category_name, category_id)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (update.id, update.channel, update.timestamp, update.title, update.category_name, update.category_id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        return update_id
    
    async def get_twitch_update(self, id:str) -> TwitchChannelUpdate | None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {TwitchChannelUpdate.table_name}
            WHERE id = {self.char};
            """,
            (id,)
        )
        args = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        if args:
            return TwitchChannelUpdate(*args)
        else:
            return None

    async def add_youtube_video(self, video: YoutubeVideo) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {YoutubeVideo.table_name} 
            (id, uploaded)
            VALUES
            ({self.char}, {self.char});
            """,
            (YoutubeVideo.id, YoutubeVideo.uploaded)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
    
    async def youtube_video_uploaded(self, video: YoutubeVideo) -> YoutubeVideo:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            UPDATE youtube_video
            SET uploaded = {self.char}
            WHERE id = {self.char};
            """,
            (True, video.id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        video.uploaded = True
        return video
    
    async def get_youtube_video(self, id:str) -> YoutubeVideo | None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM {YoutubeVideo.table_name}
            WHERE id = {self.char};
            """,
            (id,)
        )
        args = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        if args:
            return YoutubeVideo(*args)
        else:
            return None
    
    async def add_video_file(self, video: VideoFile) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {VideoFile.table_name} 
            (id, stream, channel, quality, path, started_at, ended_at, part)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (video.id, video.stream, video.channel, video.quality, video.path.__str__(), video.started_at, video.ended_at, video.part)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
    
    async def end_video_file(self, video: VideoFile, ended_at:datetime) -> VideoFile:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            UPDATE {VideoFile.table_name}
            SET ended_at = {self.char}
            WHERE id = {self.char};
            """,
            (ended_at, video.id)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
        video.ended_at = ended_at
        return video
    
    async def get_video_file(self, id:str|None, path:Path|None) -> VideoFile | None:

        if id == path == None:
            raise Exception('One of "id" or "path" must be specified')
        i = iter([id, path])
        if not (any(i) and not any(i)):
            raise Exception('Only one of "id" or "path" must be specified')
        
        connection = await self.connect()
        cursor = await connection.cursor()
        if id:
            await cursor.execute(
                f"""
                SELECT * FROM {VideoFile.table_name}
                WHERE id = {self.char};
                """,
                (id,)
            )
        elif path:
            await cursor.execute(
                f"""
                SELECT * FROM {VideoFile.table_name}
                WHERE path = {self.char};
                """,
                (path.__str__(),)
            )
        args = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        if args:
            return VideoFile(*args)
        else:
            return None
    
    async def set_twitch_client(self, client_id:str, client_secret:str) -> None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {TwitchClient.table_name}
            (id, client_id, client_secret)
            VALUES
            ({self.char}, {self.char}, {self.char})
            {self.duplicate('id')}
            client_id={self.char}, client_secret={self.char};
            """,
            (CLIENT_NUM, client_id, client_secret, client_id, client_secret)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()
    
    async def get_twitch_client(self) -> tuple[str, str]|None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT client_id, client_secret
            FROM {TwitchClient.table_name}
            WHERE id = {self.char}
            """,
            (CLIENT_NUM,)
        )
        result = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        return result
    
    async def set_twitch_auth(self, token, refresh_token):
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO {TwitchAuth.table_name} 
            (id, auth_token, refresh_token)
            VALUES
            ({self.char}, {self.char}, {self.char})
            {self.duplicate('id')}
            auth_token={self.char}, refresh_token={self.char};
            """,
            (CLIENT_NUM, token, refresh_token, token, refresh_token)
        )
        await connection.commit()
        await cursor.close()
        await connection.close()

    async def get_twitch_auth(self) -> tuple[str, str]|None:
        connection = await self.connect()
        cursor = await connection.cursor()
        await cursor.execute(
            f"""
            SELECT auth_token, refresh_token
            FROM {TwitchAuth.table_name}
            WHERE id = {self.char}
            """,
            (CLIENT_NUM,)
        )
        result = await cursor.fetchone()
        await cursor.close()
        await connection.close()
        return result

class SQLLiteDatabase(BaseDatabase):

    char = '?'

    def __init__(self, path) -> None:
        self.path = Path(path)
        super().__init__()

    async def connect(self):
        connection = await aiosqlite.connect(self.path)
        return connection
    
    def duplicate(self, column:str):
        return f'ON CONFLICT({column}) DO UPDATE SET'

class MySQLDatabase(BaseDatabase):

    char = '%s'

    def __init__(
            self,
            host: str,
            port: str|int,
            channel: str,
            password: str,
            schema: str,
        ) -> None:
        self.host=host
        self.port=port
        self.channel=channel
        self.password=password
        self.schema=schema
        super().__init__()

    async def connect(self):
        connection = await aiomysql.connect(
            host=self.host,
            port=self.port,
            channel=self.channel,
            password=self.password,
            db=self.schema,
            loop=asyncio.get_event_loop(),
        )
        return connection

async def get_db() -> BaseDatabase:

    if 'DB_TYPE' not in os.environ:
        os.environ['DB_TYPE'] = DEFAULT_TYPE

    if os.environ['DB_TYPE'].lower() == 'sqlite':
        if 'DB_PATH' not in os.environ:
            os.environ['DB_PATH'] = DEFAULT_PATH
        database = await SQLLiteDatabase.create('test.sql')

    elif os.environ['DB_TYPE'].lower() == 'mysql':
        database = await MySQLDatabase.create(
            host=os.environ['DB_HOST'],
            port=os.environ['DB_PORT'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS'],
            schema=os.environ['DB_SCHEMA'],
        )

    else:
        raise RuntimeError('"DB_TYPE" must be either "sqlite" or "mysql"')
    
    return database
