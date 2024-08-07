import aiosqlite
from pathlib import Path
from datetime import datetime
from twitchAPI.object.eventsub import StreamOnlineData, StreamOfflineData, ChannelUpdateData
import asyncio
from datetime import datetime
from uuid import uuid4
from twitchAPI.twitch import Stream

CLIENT_NUM = 0

class BaseDatabase():

    char = None
    connection = None

    def __init__(self) -> None:
        pass

    @classmethod
    async def create(cls, *args, **kwargs):
        database = cls(*args, **kwargs)
        await database.connect()
        await database.initialize()
        return database

    async def connect(self) -> None:
        pass

    async def initialize(self) -> None:
        cursor = await self.connection.cursor()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS twitch_user (
                id UNSIGNED BIGINT NOT NULL UNIQUE,
                login VARCHAR(25) NOT NULL UNIQUE,
                name VARCHAR(25) NOT NULL UNIQUE,
                active BOOL NOT NULL DEFAULT 0,
                quality VARCHAR(8),
                PRIMARY KEY (id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS twitch_stream (
                id UNSIGNED BIGINT NOT NULL UNIQUE,
                user UNSIGNED INT NOT NULL,
                title VARCHAR(140) NOT NULL,
                category_name VARCHAR(256) NOT NULL,
                category_id UNSIGNED INT NOT NULL,
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY (user) REFERENCES twitch_user(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS twitch_channel_update (
                id VARCHAR(36) NOT NULL UNIQUE,
                user UNSIGNED INT NOT NULL,
                timestamp DATETIME NOT NULL,
                title VARCHAR(140) NOT NULL,
                category_name VARCHAR(256) NOT NULL,
                category_id id UNSIGNED INT NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY (user) REFERENCES twitch_user(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_video (
                id VARCHAR(12) NOT NULL UNIQUE,
                video UNSIGNED INT NOT NULL UNIQUE,
                uploaded BOOL NOT NULL DEFAULT 0,
                PRIMARY KEY (id),
                FOREIGN KEY (video) REFERENCES video_file(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS video_file (
                id VARCHAR(36) NOT NULL UNIQUE,
                stream UNSIGNED INT NOT NULL,
                user UNSIGNED INT NOT NULL,
                quality VARCHAR(8),
                path VARCHAR(4096),
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                part UNSIGNED SMALLINT NOT NULL DEFAULT 0,
                PRIMARY KEY (id),
                FOREIGN KEY (stream) REFERENCES twitch_stream(id),
                FOREIGN KEY (user) REFERENCES twitch_user(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS twitch_client (
                id INT NOT NULL UNIQUE,
                client_id VARCHAR(30) NOT NULL,
                client_secret VARCHAR(30) NOT NULL,
                PRIMARY KEY (id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS twitch_auth (
                id INT NOT NULL UNIQUE,
                auth_token VARCHAR(30) DEFAULT NULL,
                refresh_token VARCHAR(50) DEFAULT NULL,
                PRIMARY KEY (id)
            );
            """
        )
        await self.connection.commit()
        await cursor.close()

    # Low level functions

    async def add_twitch_user(
            self,
            id:str|int,
            login:str,
            name:str,
            active:bool,
            quality:str,
        ):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_user 
            (id, login, name, active, quality)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char})
            ON CONFLICT(id) DO UPDATE SET
            active={self.char}, quality={self.char};
            """,
            (id, login, name, active, quality, active, quality)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def get_twitch_user(
            self,
            id:str|int|None=None,
            login:str|None=None,
            name:str|None=None,
        ):

        if id == login == name == None:
            raise Exception('One of "id", "login", or "name" must be specified')
        i = iter([id, login, name])
        if not (any(i) and not any(i)):
            raise Exception('Only one of "id", "login", or "name" must be specified')
        
        cursor = await self.connection.cursor()
        if id:
            await cursor.execute(
                f"""
                SELECT * FROM twitch_user
                WHERE id = {self.char};
                """,
                (id,)
            )
        elif login:
            await cursor.execute(
                f"""
                SELECT * FROM twitch_user
                WHERE login = {self.char};
                """,
                (login,)
            )
        elif name:
            await cursor.execute(
                f"""
                SELECT * FROM twitch_user
                WHERE name = {self.char};
                """,
                (name,)
            )
        twitch_user = await cursor.fetchone()
        return twitch_user

    async def add_twitch_stream(
            self,
            id:str|int,
            user:str|int,
            title:str,
            category_name:str,
            category_id:str|int,
            started_at:datetime,
            ended_at:datetime=None
        ):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_stream 
            (id, user, title, category_name, category_id, started_at, ended_at)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (id, user, title, category_name, category_id, started_at, ended_at)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def end_twitch_stream(self, id:str|int, ended_at:datetime):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            UPDATE twitch_stream
            SET ended_at = {self.char}
            WHERE id = {self.char};
            """,
            (ended_at, id)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def get_twitch_stream(self, id:str|int):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM twitch_stream
            WHERE id = {self.char}
            """,
            (id,)
        )
        twitch_stream = await cursor.fetchone()
        return twitch_stream

    async def add_twitch_update(
            self,
            user:str|int,
            timestamp:datetime,
            title:str,
            category_name:str,
            category_id:str|int
        ):
        update_id = uuid4().__str__()
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_channel_update
            (id, user, timestamp, title, category_name, category_id)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (update_id, user, timestamp, title, category_name, category_id)
        )
        await self.connection.commit()
        await cursor.close()
        return update_id
    
    async def get_twitch_update(self, id:str):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM twitch_channel_update
            WHERE id = {self.char};
            """,
            (id,)
        )
        twitch_stream = await cursor.fetchone()
        return twitch_stream

    async def add_youtube_video(self, id:str, uploaded:bool=False):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO youtube_video 
            (id, uploaded)
            VALUES
            ({self.char}, {self.char});
            """,
            (id, uploaded)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def youtube_video_uploaded(self, id:str, uploaded:bool = True):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            UPDATE youtube_video
            SET uploaded = {self.char}
            WHERE id = {self.char};
            """,
            (uploaded, id)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def get_youtube_video(self, id:str):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            SELECT * FROM youtube_video
            WHERE id = {self.char};
            """,
            (id,)
        )
        twitch_stream = await cursor.fetchone()
        return twitch_stream
    
    async def add_video_file(
            self,
            stream:str|int,
            user:str|int,
            quality:str,
            path:Path,
            started_at:datetime,
            ended_at:datetime = None,
            part:str|int = 0,
        ):
        video_id = uuid4().__str__()
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO video_file 
            (id, stream, user, quality, path, started_at, ended_at, part)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (video_id, stream, quality, path, user, started_at, ended_at, part)
        )
        await self.connection.commit()
        await cursor.close()
        return video_id
    
    async def end_video_file(self, id:str|int, ended_at:datetime):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            UPDATE video_file
            SET ended_at = {self.char}
            WHERE id = {self.char};
            """,
            (ended_at, id)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def get_video_file(self, id:str, path:Path):

        if id == path == None:
            raise Exception('One of "id" or "path" must be specified')
        i = iter([id, path])
        if not (any(i) and not any(i)):
            raise Exception('Only one of "id" or "path" must be specified')
        
        cursor = await self.connection.cursor()
        if id:
            await cursor.execute(
                f"""
                SELECT * FROM video_file
                WHERE id = {self.char};
                """,
                (id,)
            )
        elif path:
            await cursor.execute(
                f"""
                SELECT * FROM video_file
                WHERE path = {self.char};
                """,
                (path,)
            )
        video_file = await cursor.fetchone()
        await cursor.close()
        return video_file
    
    async def set_twitch_client(self, client_id:str, client_secret:str):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_client
            (id, client_id, client_secret)
            VALUES
            ({self.char}, {self.char}, {self.char})
            ON CONFLICT(id) DO UPDATE SET
            client_id={self.char}, client_secret={self.char};
            """,
            (CLIENT_NUM, client_id, client_secret, client_id, client_secret)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def get_twitch_client(self) -> tuple[str, str]|None:
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            SELECT client_id, client_secret
            FROM twitch_client
            WHERE id = {self.char}
            """,
            (CLIENT_NUM,)
        )
        result = await cursor.fetchone()
        await cursor.close()
        return result
    
    async def set_twitch_auth(self, token, refresh_token):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_auth 
            (id, auth_token, refresh_token)
            VALUES
            ({self.char}, {self.char}, {self.char})
            ON CONFLICT(id) DO UPDATE SET
            auth_token={self.char}, refresh_token={self.char};
            """,
            (CLIENT_NUM, token, refresh_token, token, refresh_token)
        )
        await self.connection.commit()
        await cursor.close()

    async def get_twitch_auth(self) -> tuple[str, str]|None:
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            SELECT auth_token, refresh_token
            FROM twitch_auth
            WHERE id = {self.char}
            """,
            (CLIENT_NUM,)
        )
        result = await cursor.fetchone()
        await cursor.close()
        return result

    # High level functions

    async def on_channel_update(self, data:ChannelUpdateData):
        update_id = await self.add_twitch_update(
            user=data.broadcaster_user_id,
            timestamp=datetime.now(),
            title=data.title,
            category_name=data.category_name,
            category_id=data.category_id
        )
        return update_id
    
    async def on_stream_online(self, data:StreamOnlineData, stream:Stream):
        await self.add_twitch_stream(
            id=data.id,
            user=data.broadcaster_user_id,
            title=stream.title,
            category_id=stream.game_id,
            category_name=stream.game_name,
            started_at=data.started_at
        )

    async def on_stream_offline(self, data:StreamOfflineData):
        pass


class SQLLiteDatabase(BaseDatabase):

    char = '?'

    def __init__(self, path) -> None:
        self.path = Path(path)
        super().__init__()

    async def connect(self) -> None:
        self.connection = await aiosqlite.connect(self.path)

class MySQLDatabase(BaseDatabase):

    char = '%s'

    def __init__(self) -> None:
        super().__init__()
