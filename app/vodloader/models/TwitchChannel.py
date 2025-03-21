from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel, TwitchClient
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream

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
    
    def get_stream(self, quality=None, token=None) -> TwitchHLSStream:
        if quality == None:
            quality = self.quality
        session = streamlink.Streamlink(options={
            'retry-max': 0,
            'retry-open': 5,
        })
        return session.streams(self.get_url())[quality]
    
    def get_url(self):
        return f'https://twitch.tv/{self.login}'

    async def is_live(self):
        live = False
        twitch = await TwitchClient.get_twitch()
        if type(user_id) is int:
            user_id = f'{user_id}'
        data = await first(twitch.get_streams(user_id=user_id))
        if data == None:
            return False
        elif data.type == 'live':
            return True
        else:
            return False

    def __str__(self):
        return self.id
