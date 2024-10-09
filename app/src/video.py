import logging
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream
from twitchAPI.object.api import Stream
import logging
from pathlib import Path
from datetime import datetime, timezone
from .models import *
from uuid import uuid4
from threading import Thread
import asyncio

CHUNK_SIZE = 8192
MAX_VIDEO_LENGTH = 60*(60*12-15)
RETRY_COUNT = 10
VIDEO_EXTENSION = 'ts'
MAX_LENGTH=60*(60*12-15)

class Video():

    def __init__(self, id, url, channel, channel_id, path, quality='best'):
        
        self.logger = logging.getLogger(f'vodloader.{channel}.{type(self).__name__}')
        self.stream_id = id
        self.url = url
        self.channel = channel
        self.channel_id = channel_id
        self.path = Path(path)
        self.quality = quality
        self.video_id = None
        self.download_thread = None
        self.stream = self.get_stream()
        
    def get_stream(self, token=None) -> TwitchHLSStream:
        session = streamlink.Streamlink(options={
            'stream-segment-timeout': 30.0,
            'stream-timeout': 60.0,

        })
        return session.streams(self.url)[self.quality]

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
            data = buffer.read(CHUNK_SIZE)
            while data:
                f.write(data)
                data = buffer.read(CHUNK_SIZE)
        buffer.close()

class LiveStream(Video):
    
    def __init__(self, stream:Stream, directory:Path, quality='best'):
        self.name = f'{stream.user_login}-{stream.title}-{stream.id}.{VIDEO_EXTENSION}'
        super().__init__(
            id=stream.id,
            url=f'https://twitch.tv/{stream.user_login}',
            channel=stream.user_login,
            channel_id=stream.user_id,
            path=directory.joinpath(self.name),
            quality=quality
        )

class VOD(Video):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
