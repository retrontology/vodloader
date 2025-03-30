from vodloader.database import *
from vodloader.util import *
from vodloader import config
from vodloader.models import BaseModel
from vodloader.twitch import twitch
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream
from twitchAPI.helper import first
from twitchAPI.twitch import Stream
from typing import Self


RETRY_LIMIT = 10


class TwitchChannel(BaseModel):


    table_name = 'twitch_channel'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT UNSIGNED NOT NULL UNIQUE,
            login VARCHAR(25) NOT NULL UNIQUE,
            name VARCHAR(25) NOT NULL UNIQUE,
            active BOOL NOT NULL DEFAULT 0,
            quality VARCHAR(8),
            webhook_online VARCHAR(64),
            webhook_offline VARCHAR(64),
            webhook_update VARCHAR(64),
            PRIMARY KEY (id)
        );
        """


    id: int
    login: str
    name: str
    active: bool
    quality: str
    webhook_online: str
    webhook_offline: str
    webhook_update: str


    def __init__(
            self,
            id: str|int,
            login: str,
            name: str,
            active: bool = True,
            quality: str = 'best',
            webhook_online: str = None,
            webhook_offline: str = None,
            webhook_update: str = None,
        ) -> None:

        super().__init__()
        self.id = int(id)
        self.login = login
        self.name = name
        self.active = active
        self.quality = quality
        self.webhook_online = webhook_online
        self.webhook_offline = webhook_offline
        self.webhook_update = webhook_update

    
    # Factory for making a TwitchChannel just from a Channel name
    @classmethod
    async def from_name(cls, name, quality="best") -> Self|None:

        channel = await first(twitch.get_users(logins=[name]))

        if not channel:
            return None

        return cls(
            id = channel.id,
            login = channel.login,
            name = channel.display_name,
            quality = quality,
        )


    async def activate(self):
        self.active = True
        await self.save()


    async def deactivate(self):
        self.active = False
        await self.save()


    def get_video_stream(self, quality=None, token=None) -> TwitchHLSStream:
        if quality == None:
            quality = self.quality
        session = streamlink.Streamlink(options={
            'retry-max': 0,
            'retry-open': 5,
        })
        return session.streams(self.get_url())[quality]


    async def get_stream_info(self) -> Stream:
        stream_info = None
        count = 0
        while stream_info == None:
            stream_info = await first(twitch.get_streams(user_id=f'{self.id}'))
            if stream_info == None:
                count += 1
                if count >= RETRY_LIMIT:
                    raise StreamUnretrievable()
                else:
                    self.logger.warning(f'Could not retrieve current livestream from Twitch. Retrying #{count}/{RETRY_LIMIT}')
                    await asyncio.sleep(5)
            else:
                return stream_info


    def get_url(self):
        return f'https://twitch.tv/{self.login}'


    async def is_live(self):
        live = False
        if type(user_id) is int:
            user_id = f'{user_id}'
        data = await first(twitch.get_streams(user_id=user_id))
        if data == None:
            return False
        elif data.type == 'live':
            return True
        else:
            return False
    
    def get_path(self):
        return config.DOWNLOAD_DIR.joinpath(self.login)

    def __str__(self):
        return self.id


class StreamUnretrievable(Exception): pass
