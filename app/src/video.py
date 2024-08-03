import logging
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream
from twitchAPI.twitch import Twitch
from twitchAPI.object.api import Stream
import logging
from pathlib import Path

CHUNK_SIZE = 8192
MAX_VIDEO_LENGTH = 60*(60*12-15)
RETRY_COUNT = 10
VIDEO_EXTENSION = 'ts'

class Video():

    def __init__(self, id, url, channel, path, quality='best'):
        self.logger = logging.getLogger(f'vodloader.{channel}.{type(self).__name__}')
        self.id = id
        self.url = url
        self.channel = channel
        self.path = path
        self.quality = quality
        self.stream = self.get_stream()
        
    def get_stream(self) -> TwitchHLSStream:
        return streamlink.streams(self.url)[self.quality]

    async def download_stream(
            self,
            chunk_size=CHUNK_SIZE,
            max_length=MAX_VIDEO_LENGTH,
        ):
        self.logger.info(f'Downloading stream from {self.url} to {self.path}')
        stream = self.get_stream()
        buffer = stream.open()
        with open(self.path, 'wb') as f:
            data = buffer.read(chunk_size)
            while data:
                f.write(data)
                data = buffer.read(chunk_size)
        buffer.close()
        self.logger.info(f'Finished downloading stream from {self.url} to {self.path}')

class LiveStream(Video):
    
    def __init__(self, stream:Stream, directory:Path, quality='best'):
        self.name = f'{stream.user_login}-{stream.id}.{VIDEO_EXTENSION}'
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
