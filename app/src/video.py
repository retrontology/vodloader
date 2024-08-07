import logging
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream
from twitchAPI.object.api import Stream
import logging
from pathlib import Path
from .database import BaseDatabase
from datetime import datetime

CHUNK_SIZE = 8192
MAX_VIDEO_LENGTH = 60*(60*12-15)
RETRY_COUNT = 10
VIDEO_EXTENSION = 'ts'

class Video():

    def __init__(self, database:BaseDatabase, id, url, channel, path, quality='best'):
        self.logger = logging.getLogger(f'vodloader.{channel}.{type(self).__name__}')
        self.database = database
        self.stream_id = id
        self.url = url
        self.channel = channel
        self.path = Path(path)
        self.quality = quality
        self.video_id = None
        self.stream = self.get_stream()
        
    def get_stream(self) -> TwitchHLSStream:
        return streamlink.streams(self.url)[self.quality]

    async def download_stream(
            self,
            chunk_size=CHUNK_SIZE,
        ):
        self.logger.info(f'Downloading stream from {self.url} to {self.path}')
        self.video_id = await self.database.add_video_file(
            stream=self.stream_id,
            user=self.channel,
            quality=self.quality,
            path=self.path,
            started_at=datetime.now(),
        )
        stream = self.get_stream()
        buffer = stream.open()
        with open(self.path, 'wb') as f:
            data = buffer.read(chunk_size)
            while data:
                f.write(data)
                data = buffer.read(chunk_size)
        buffer.close()
        await self.database.end_video_file(
            id=self.video_id,
            ended_at=datetime.now()
        )
        self.logger.info(f'Finished downloading stream from {self.url} to {self.path}')

class LiveStream(Video):
    
    def __init__(self, stream:Stream, directory:Path, quality='best'):
        self.name = f'{stream.user_login}-{stream.title}-{stream.id}.{VIDEO_EXTENSION}'
        super().__init__(
            id=stream.id,
            url=f'https://twitch.tv/{stream.user_login}',
            channel=stream.user_login,
            path=directory.joinpath(self.name),
            quality=quality
        )

class VOD(Video):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
