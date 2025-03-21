from .channel import Channel
from .models import *
from .chat import Bot
from twitchAPI.twitch import Twitch
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
            chat=self.chat
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

    def transcode_loop(self):
        loop = asyncio.new_event_loop()
        while True:
            video = loop.run_until_complete(VideoFile.get_next_transcode())
            if video:
                loop.run_until_complete(video.transcode())
            else:
                loop.run_until_complete(asyncio.sleep(60))
    
    async def download_stream(self):
        self.logger.info(f'Downloading stream from {self.url} to {self.path}')
        video_file = VideoFile(
            id=uuid4().__str__(),
            stream=self.stream_id,
            channel=self.channel_id,
            quality=self.quality,
            path=self.path,
            started_at=datetime.now(timezone.utc),
        )
        await video_file.save()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._download)
        await video_file.end()
        self.logger.info(f'Finished downloading stream from {self.url} to {self.path}')
    
    def _download(self):
        stream = self.get_stream()
        buffer = stream.open()
        with open(self.path, 'wb') as f:
            while not self.ended:
                try:
                    data = buffer.read(CHUNK_SIZE)
                    while data:
                        f.write(data)
                        data = buffer.read(CHUNK_SIZE)
                except Exception as e:
                    self.logger.error(e)
        buffer.close()

    


class ChannelAlreadyAdded(Exception): pass
class ChannelNotAdded(Exception): pass
