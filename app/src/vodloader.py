from .database import BaseDatabase
from .channel import Channel
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
        self.download_dir = download_dir
        self.channels = []


    async def start(self):
        channels = await self.database.get_twitch_users()

        for channel in channels:
            channel = await Channel.create(
                database=self.database,
                channel_name,
                download_dir=self.download_dir,
                twitch=self.twitch,
                eventsub=self.eventsub,
                channel_config['quality'],
            )
            channels.append(channel)