from datetime import datetime
from pathlib import Path
from typing import Self, List
from vodloader.database import *
from vodloader.util import *
from vodloader.models import EndableModel, TwitchStream, TwitchChannel, OrderDirection, NOT_NULL


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
            part TINYINT UNSIGNED DEFAULT 1,
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
