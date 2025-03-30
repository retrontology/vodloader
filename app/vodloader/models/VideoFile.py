from datetime import datetime
from pathlib import Path
from typing import Self, List
from vodloader.database import *
from vodloader.util import *
from vodloader.models import EndableModel, TwitchStream, TwitchChannel, OrderDirection, NOT_NULL
import ffmpeg


class VideoFile(EndableModel):

    table_name = 'video_file'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            stream BIGINT UNSIGNED NOT NULL,
            channel INT UNSIGNED NOT NULL,
            quality VARCHAR(8),
            path VARCHAR(4096),
            started_at DATETIME NOT NULL,
            ended_at DATETIME DEFAULT NULL,
            transcode_path VARCHAR(4096) DEFAULT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (stream) REFERENCES {TwitchStream.table_name}(id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """

    id: str
    stream: int
    channel: int
    quality: int
    path: Path
    started_at: datetime
    ended_at: datetime
    part: int
    transcode_path: Path
    

    def __init__(
            self,
            id: str,
            stream: str|int,
            channel: str|int,
            quality: str,
            path: str|Path,
            started_at: datetime,
            ended_at: datetime = None,
            part: int = 1,
            transcode_path: str|Path = None,
    ) -> None:
        
        super().__init__()
        self.id = id
        self.stream = int(stream)
        self.channel = int(channel)
        self.quality = quality
        self.path = Path(path).resolve()
        self.started_at = started_at
        self.ended_at = ended_at
        self.part = part
        self.transcode_path = Path(transcode_path).resolve() if transcode_path else None

    @classmethod
    async def get_nontranscoded(cls) -> List[Self]:
        results = await cls.get_many(
            transcode_path=None,
            order_by='started_at',
            order=OrderDirection.ASC
        )
        return results

    @classmethod
    async def get_next_transcode(cls) -> Self:
        next = await cls.get(
            transcode_path=None,
            ended_at=NOT_NULL,
            order_by='started_at',
            order=OrderDirection.ASC
        )
        return next
    
    async def remove_original(self):
        
        if not self.path:
            raise VideoAlreadyRemoved
        
        path = self.path
        self.path.unlink()
        self.path = None
        await self.save()
        self.logger.info(f'The original stream file at {path.__str__()} has been deleted')
    
    async def transcode(self):

        if not self.ended_at:
            raise VideoFileNotEnded
        
        if self.transcode_path:
            raise VideoAlreadyTranscoded
        
        self.logger.info(f'Transcoding {self.path}')
        loop = asyncio.get_event_loop()
        self.transcode_path = await loop.run_in_executor(None, self._transcode)
        await self.save()
        self.logger.info(f'Finished transcoding {self.path} to {self.transcode_path}')
        await self.remove_original()
        

    def _transcode(self) -> Path:
        transcode_path = self.path.parent.joinpath(f'{self.path.stem}.mp4')
        stream = ffmpeg.input(self.path.__str__())
        stream = ffmpeg.output(stream, transcode_path.__str__(), vcodec='copy')
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream, quiet=True)
        return transcode_path

class VideoFileNotEnded(Exception): pass
class VideoAlreadyTranscoded(Exception): pass
class VideoAlreadyRemoved(Exception): pass
