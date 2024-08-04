import aiosqlite
from pathlib import Path
from datetime import datetime
from twitchAPI.object.eventsub import StreamOnlineData, StreamOfflineData, ChannelUpdateData

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
                id INT PRIMARY KEY,
                user UNSIGNED INT NOT NULL,
                timestamp DATETIME NOT NULL,
                title VARCHAR(140) NOT NULL,
                category_name VARCHAR(256) NOT NULL,
                category_id id USIGNED INT NOT NULL,
                FOREIGN KEY (user) REFERENCES twitch_user(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_video (
                id VARCHAR(12) NOT NULL UNIQUE,
                video USIGNED INT NOT NULL UNIQUE,
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
                id INT PRIMARY KEY,
                stream UNSIGNED INT NOT NULL,
                user UNSIGNED INT NOT NULL,
                started_at DATETIME NOT NULL,
                ended_at DATETIME,
                part UNSIGNED SMALLINT NOT NULL DEFAULT 0,
                FOREIGN KEY (stream) REFERENCES twitch_stream(id),
                FOREIGN KEY (user) REFERENCES twitch_user(id)
            );
            """
        )
        await self.connection.commit()
        await cursor.close()

    async def add_twitch_user(self, id:str|int, login:str, name:str, active:bool):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_user 
            (id, login, name, active)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char})
            ON CONFLICT(id) DO UPDATE SET
            active={self.char};
            """,
            (id, login, name, active, active)
        )
        await self.connection.commit()
        await cursor.close()

    # Low level functions

    async def add_twitch_stream(
            self,
            id:str|int,
            user:str|int,
            started_at:datetime,
            ended_at:datetime=None
        ):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_stream 
            (id, user, started_at, ended_at)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char});
            """,
            (id, user, started_at, ended_at)
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

    async def add_twitch_update(
            self,
            user:str|int,
            timestamp:datetime,
            title:str,
            category_name:str,
            category_id:str|int
        ):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO twitch_channel_update
            (user, timestamp, title, category_name, category_id)
            VALUES
            ({self.char}, {self.char}, {self.char}, {self.char}, {self.char});
            """,
            (user, timestamp, title, category_name, category_id)
        )
        await self.connection.commit()
        await cursor.close()

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
    
    async def add_video_file(
            self,
            stream:str|int,
            user:str|int,
            started_at: datetime,
            ended_at:datetime = None,
            part:str|int = 0,
        ):
        cursor = await self.connection.cursor()
        await cursor.execute(
            f"""
            INSERT INTO video_file 
            (stream, user, started_at, ended_at, part)
            VALUES
            ({self.char}, {self.char});
            """,
            (stream, user, started_at, ended_at, part)
        )
        await self.connection.commit()
        await cursor.close()
    
    async def youtube_video_uploaded(self, id:str, ended_at:datetime):
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

    # High level functions

    async def on_channel_update(self, data:ChannelUpdateData):
        await self.add_twitch_update(
            user=data.broadcaster_user_id,
            timestamp=datetime.now(),
            title=data.title,
            category_name=data.category_name,
            category_id=data.category_id
        )
    
    async def on_stream_online(self, data:StreamOnlineData):
        await self.add_twitch_stream(
            id=data.id,
            user=data.broadcaster_user_id,
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
