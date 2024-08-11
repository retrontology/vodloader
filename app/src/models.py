from datetime import datetime
from pathlib import Path
from typing import List


class Model(): 
    
    table_name:str = None
    table_command:str = None

    def __eq__(self, other):
        return self.name == other.name and self.age == other.age


class TwitchChannel(Model):

    table_name = 'twitch_channel'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT UNSIGNED NOT NULL UNIQUE,
            login VARCHAR(25) NOT NULL UNIQUE,
            name VARCHAR(25) NOT NULL UNIQUE,
            active BOOL NOT NULL DEFAULT 0,
            quality VARCHAR(8),
            PRIMARY KEY (id)
        );
        """

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

    table_name = 'twitch_stream'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGINT UNSIGNED NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            title VARCHAR(140) NOT NULL,
            category_name VARCHAR(256) NOT NULL,
            category_id INT UNSIGNED NOT NULL,
            started_at DATETIME NOT NULL,
            ended_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """
    
    id: int
    channel: int
    title: str
    category_name: str
    category_id: int
    started_at: datetime
    ended_at: datetime

    def __init__(
            self,
            id: str|int,
            channel: str|int,
            title: str,
            category_name: str,
            category_id: str|int,
            started_at: datetime,
            ended_at: datetime = None,
    ) -> None:
        
        self.id = int(id)
        self.channel = int(channel)
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)
        self.started_at = started_at
        self.ended_at = ended_at


class TwitchChannelUpdate(Model):

    table_name = 'twitch_channel_update'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            channel INT UNSIGNED NOT NULL,
            timestamp DATETIME NOT NULL,
            title VARCHAR(140) NOT NULL,
            category_name VARCHAR(256) NOT NULL,
            category_id INT UNSIGNED NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (channel) REFERENCES {TwitchChannel.table_name}(id)
        );
        """
    
    id: str
    channel: int
    timestamp: datetime
    title: str
    category_name: str
    category_id: int

    def __init__(
            self,
            id: str,
            channel: str|int,
            timestamp: datetime,
            title: str,
            category_name: str,
            category_id: str|int
    ) -> None:
        
        self.id = id
        self.channel = int(channel)
        self.timestamp = timestamp
        self.title = title
        self.category_name = category_name
        self.category_id = int(category_id)


class VideoFile(Model):

    table_name = 'video_file'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id VARCHAR(36) NOT NULL UNIQUE,
            stream BIGINT UNSIGNED NOT NULL,
            channel INT UNSIGNED NOT NULL,
            quality VARCHAR(8),
            path VARCHAR(4096),
            started_at DATETIME NOT NULL,
            ended_at DATETIME,
            part SMALLINT UNSIGNED NOT NULL DEFAULT 1,
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

    def __init__(
            self,
            id: str,
            stream: str|int,
            channel: str|int,
            quality: str,
            path: str|Path,
            started_at: datetime,
            ended_at: datetime = None,
            part: str|int = 1
    ) -> None:
        
        self.id = id
        self.stream = int(stream)
        self.channel = int(channel)
        self.quality = quality
        self.path = Path(path)
        self.started_at = started_at
        self.ended_at = ended_at
        self.part = int(part)


class YoutubeVideo(Model):

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
        
        self.id = id
        self.video = video
        self.uploaded = uploaded


class TwitchClient(Model):

    table_name = 'twitch_client'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            client_id VARCHAR(30) NOT NULL,
            client_secret VARCHAR(30) NOT NULL,
            PRIMARY KEY (id)
        );
        """

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

    table_name = 'twitch_auth'
    table_command = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT NOT NULL UNIQUE,
            auth_token VARCHAR(30) DEFAULT NULL,
            refresh_token VARCHAR(50) DEFAULT NULL,
            PRIMARY KEY (id)
        );
        """

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


MODELS: List[Model] = [
    TwitchChannel,
    TwitchStream,
    TwitchChannelUpdate,
    VideoFile,
    YoutubeVideo,
    TwitchClient,
    TwitchAuth
]