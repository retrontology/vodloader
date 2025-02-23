from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel

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
