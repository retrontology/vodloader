from .database import BaseDatabase
from .channel import Channel
from .models import *
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from pathlib import Path


class VODLoader():
    
    def __init__(
            self,
            database:BaseDatabase,
            twitch:Twitch,
            eventsub:EventSubWebhook,
            download_dir:Path
    ):

        self.database = database
        self.twitch = twitch
        self.eventsub = eventsub
        self.download_dir = Path(download_dir)
        self.channels = []


    async def start(self):
        db_channels = await self.database.get_twitch_channels()
        self.channels = []
        for channel in db_channels:
            await self.add_channel(channel)

    async def add_channel(self, channel: TwitchChannel):
        channel = await Channel.create(
            database=self.database,
            name=channel.name,
            download_dir=self.download_dir,
            twitch=self.twitch,
            eventsub=self.eventsub,
            quality=channel.quality,
        )
        self.channels.append(channel)

    async def remove_channel(self, channel: TwitchChannel):
        pass
