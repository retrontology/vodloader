from .channel import Channel
from .models import *
from .chat import Bot
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

    async def start(self):
        loop = asyncio.get_event_loop()

        # Start chat bot
        self.chat = Bot()
        self.chat_thread = Thread(target=self.chat.start, daemon=True)
        self.chat_thread.start()

        # Load channels
        self.channels = {}
        db_channels = await TwitchChannel.get_many(active=True)
        if db_channels:
            for channel in db_channels:
                channel = await Channel.from_channel(
                    channel=channel,
                    download_dir=self.download_dir,
                    twitch=self.twitch,
                    eventsub=self.eventsub,
                    chat=self.chat
                )
                self.channels[channel.login] = channel

        # Run transcode loop
        self.transcode_task = Thread(target=self.transcode_loop, daemon=True)
        self.transcode_task.start()
    
    

    

    def transcode_loop(self):
        loop = asyncio.new_event_loop()
        while True:
            video = loop.run_until_complete(VideoFile.get_next_transcode())
            if video:
                loop.run_until_complete(video.transcode())
            else:
                loop.run_until_complete(asyncio.sleep(60))
    
    

    


class ChannelAlreadyAdded(Exception): pass
class ChannelNotAdded(Exception): pass
