import aiosqlite
import aiomysql
from pathlib import Path
import asyncio
from aiosqlite import Connection as SQLiteConnection
from aiomysql import Connection as MySQLConnection
import os
from vodloader import config


_database = None


class BaseDatabase():

    char = None

    def __init__(self) -> None:
        pass

    async def connect(self) -> SQLiteConnection|MySQLConnection:
        pass

    def duplicate(self, column:str) -> str:
        return 'ON DUPLICATE KEY UPDATE'


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
            user: str,
            password: str,
            schema: str,
        ) -> None:
        self.host=host
        self.port=int(port)
        self.user=user
        self.password=password
        self.schema=schema
        super().__init__()

    async def connect(self):
        connection = await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            db=self.schema,
            loop=asyncio.get_event_loop(),
        )
        return connection


async def get_db() -> BaseDatabase:
    
    if _database == None:

        match config.DB_TYPE.lower():

            case 'sqlite':
                _database = SQLLiteDatabase(config.DB_PATH)

            case 'mysql':
                _database = MySQLDatabase(
                    host=os.environ['DB_HOST'],
                    port=os.environ['DB_PORT'],
                    user=os.environ['DB_USER'],
                    password=os.environ['DB_PASS'],
                    schema=os.environ['DB_SCHEMA'],
                )

            case _:
                raise RuntimeError('"DB_TYPE" must be either "sqlite" or "mysql"')
    
    return _database
