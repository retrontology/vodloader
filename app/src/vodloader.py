from .channel import Channel
from .models import *
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from pathlib import Path
from typing import Dict


class VODLoader():

    twitch: Twitch
    eventsub: EventSubWebhook
    download_dir: Path
    channels: Dict[str, Channel]
    
    def __init__(
            self,
            twitch:Twitch,
            eventsub:EventSubWebhook,
            download_dir:Path
    ):

        self.twitch = twitch
        self.eventsub = eventsub
        self.download_dir = Path(download_dir)
        self.channels = {}


    async def start(self):
        db_channels = await TwitchChannel.get_many(active=True)
        self.channels = {}
        for channel in db_channels:
            channel = await Channel.from_channel(
                channel=channel,
                download_dir=self.download_dir,
                twitch=self.twitch,
                eventsub=self.eventsub
            )
            self.channels[channel.login] = channel

    async def add_channel(self, name: str, quality: str):

        name = name.lower()

        if channel in self.channels:
            raise RuntimeError('Channel already exists in VODLoader')

        channel = await Channel.create(
            name=name,
            download_dir=self.download_dir,
            twitch=self.twitch,
            eventsub=self.eventsub,
            quality=quality,
        )
        self.channels[channel.login] = channel

    async def remove_channel(self, name: str):
        name = name.lower()
        channel = self.channels.pop(name)
        await channel.unsubscribe()
        channel = TwitchChannel(
            id=channel.id,
            login=channel.login,
            name=channel.name,
            active=True,
            quality=channel.quality
        )
        await channel.deactivate()
