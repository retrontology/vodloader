from .channel import Channel
from .models import *
from .chat import Bot, Message
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from pathlib import Path
from typing import Dict
from threading import Thread


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
        self.chat = None

    def on_welcome(self, conn, event):
        for channel in self.channels:
            self.chat.join_channel(channel)

    def on_message(self, message: Message):
        if message.channel in self.channels:
            self.channels[message.channel].on_message(message)

    async def start(self):
        loop = asyncio.get_event_loop()

        # Load channels
        self.channels = {}
        db_channels = await TwitchChannel.get_many(active=True)
        if db_channels:
            for channel in db_channels:
                channel = await Channel.from_channel(
                    channel=channel,
                    download_dir=self.download_dir,
                    twitch=self.twitch,
                    eventsub=self.eventsub
                )
                self.channels[channel.login] = channel

        # Start chat bot
        self.chat = Bot()
        self.chat.welcome_callback = self.on_welcome
        self.chat_thread = Thread(target=self.chat.start)
        self.chat_thread.start()

        # Run transcode loop
        self.transcode_task = loop.create_task(self.transcode_loop())
        await self.transcode_task
    
    async def stop(self):
        pass

    async def add_channel(self, name: str, quality: str = 'best'):

        name = name.lower()

        if name in self.channels:
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
        if name not in self.channels:
            raise ChannelNotAdded
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

    async def transcode_loop(self):
        while True:
            video = await VideoFile.get_next_transcode()
            if video:
                await video.transcode()
            else:
                await asyncio.sleep(60)

class ChannelAlreadyAdded(Exception): pass
class ChannelNotAdded(Exception): pass
