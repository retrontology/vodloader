import logging
import streamlink
from streamlink.plugins.twitch import TwitchHLSStream
from twitchAPI.object.api import Stream
import logging
from pathlib import Path
from .database import get_db
from datetime import datetime, timezone
from .models import *
from uuid import uuid4

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
        self.stream = self.get_stream()
        
    def get_stream(self, token=None) -> TwitchHLSStream:
        session = streamlink.Streamlink()
        if token:
            session.set_option('http-headers', {'Authorization': f'OAuth {token}'})
        return session.streams(self.url)[self.quality]

    async def download_stream(
            self,
            chunk_size=CHUNK_SIZE,
        ):
        self.logger.info(f'Downloading stream from {self.url} to {self.path}')
        video_file = VideoFile(
            id=uuid4().__str__(),
            stream=self.stream_id,
            channel=self.channel_id,
            quality=self.quality,
            path=self.path,
            started_at=datetime.now(timezone.utc),
        )
        database = await get_db()
        await database.add_video_file(video_file)
        tokens = await database.get_twitch_auth()
        stream = self.get_stream(tokens[0] if tokens else None)
        buffer = stream.open()
        with open(self.path, 'wb') as f:
            data = buffer.read(chunk_size)
            while data:
                f.write(data)
                data = buffer.read(chunk_size)
        buffer.close()
        await database.end_video_file(
            video=video_file,
            ended_at=datetime.now(timezone.utc)
        )
        self.logger.info(f'Finished downloading stream from {self.url} to {self.path}')

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
