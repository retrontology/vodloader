from datetime import datetime
from pathlib import Path


class Model(): pass


class TwitchUser(Model):

    id: int
    login: str
    name: str
    active: bool
    quality: str

    def __init__(
            self,
            id: str|int,
            login: str,
            name: str,
            active: bool = True,
            quality: str = 'best',
        ) -> None:

        self.id = int(id)
        self.login = login
        self.name = name
        self.active = active
        self.quality = quality


class TwitchStream(Model):
    
    id: int
    user: int
    title: str
    category_name: str
    category_id: int
    started_at: datetime
    ended_at: datetime

    def __init__(
            self,
            id: str|int,
            user: str|int,
            title: str,
            category_name: str,
            category_id: str|int,
            started_at: datetime,
            ended_at: datetime = None,
    ) -> None:
        
        self.id = int(id)
        self.user = int(user)
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)
        self.started_at = started_at
        self.ended_at = ended_at


class TwitchChannelUpdate(Model):
    
    id: str
    user: int
    timestamp: datetime
    title: str
    category_name: str
    category_id: int

    def __init__(
            self,
            id: str,
            user: str|int,
            timestamp: datetime,
            title: str,
            category_name: str,
            category_id: str|int
    ) -> None:
        
        self.id = id
        self.user = int(user)
        self.timestamp = timestamp
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)


class VideoFile(Model):

    id: str
    stream: int
    user: int
    quality: int
    path: Path
    started_at: datetime
    ended_at: datetime
    part: int

    def __init__(
            self,
            id: str,
            stream: str|int,
            user: str|int,
            quality: str,
            path: str|Path,
            started_at: datetime,
            ended_at: datetime = None,
            part: str|int = 0
    ) -> None:
        
        self.id = id
        self.stream = int(stream)
        self.user = int(user)
        self.quality = quality
        self.path = Path(path)
        self.started_at = started_at
        self.ended_at = ended_at
        self.part = int(part)


class YoutubeVideo(Model):

    id: str
    video: str
    uploaded: bool
    
    def __init__(
            self,
            id: str,
            video: str,
            uploaded: bool = False,
    ) -> None:
        
        self.id = id
        self.video = video
        self.uploaded = uploaded


class TwitchClient(Model):

    id: int
    client_id: str
    client_secret: str

    def __init__(
            self,
            id: int|str,
            client_id: str,
            client_secret: str
    ) -> None:
        
        self.id = int(id)
        self.client_id = client_id
        self.client_secret = client_secret


class TwitchAuth(Model):

    id: int
    auth_token: str
    refresh_token: str

    def __init__(
            self,
            id: int|str,
            auth_token: str,
            refresh_token: str
    ) -> None:
        
        self.id = int(id)
        self.auth_token = auth_token
        self.refresh_token = refresh_token
