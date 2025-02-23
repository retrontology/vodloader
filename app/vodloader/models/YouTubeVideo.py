from vodloader.database import *
from vodloader.util import *
from vodloader.models import BaseModel, VideoFile


class YoutubeVideo(BaseModel):

    table_name = 'youtube_video'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(12) NOT NULL UNIQUE,
            video VARCHAR(36) NOT NULL UNIQUE,
            uploaded BOOL NOT NULL DEFAULT 0,
            PRIMARY KEY (id),
            FOREIGN KEY (video) REFERENCES {VideoFile.table_name}(id)
        );
        """

    id: str
    video: str
    uploaded: bool
    
    def __init__(
            self,
            id: str,
            video: str,
            uploaded: bool = False,
    ) -> None:
        
        super().__init__()
        self.id = id
        self.video = video
        self.uploaded = uploaded
    
    async def set_uploaded(self, uploaded: bool = True):
        self.uploaded = uploaded
        await self.save()
