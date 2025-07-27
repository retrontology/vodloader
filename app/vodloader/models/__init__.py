from .base import *
from .TwitchChannel import TwitchChannel
from .TwitchChannelUpdate import TwitchChannelUpdate
from .TwitchStream import TwitchStream
from .VideoFile import VideoFile
from .YouTubeVideo import YouTubeVideo
from .Message import Message
from .ClearChatEvent import ClearChatEvent
from .ClearMsgEvent import ClearMsgEvent
from .ChannelConfig import ChannelConfig


MODELS: List[BaseModel] = [
    TwitchChannel,
    TwitchStream,
    TwitchChannelUpdate,
    VideoFile,
    YouTubeVideo,
    Message,
    ClearChatEvent,
    ClearMsgEvent,
    ChannelConfig,
]


async def initialize_models():
    for model in MODELS:
        await model.initialize()
