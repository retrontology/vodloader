from .base import *
from .TwitchChannel import *
from .TwitchChannelUpdate import *
from .TwitchStream import *
from .VideoFile import *
from .YouTubeVideo import *
from .Message import *
from .ClearChatEvent import *
from .ClearMsgEvent import *


MODELS: List[BaseModel] = [
    TwitchChannel,
    TwitchStream,
    TwitchChannelUpdate,
    VideoFile,
    YoutubeVideo,
    Message,
    ClearChatEvent,
    ClearMsgEvent,
]


async def initialize_models():
    for model in MODELS:
        await model.initialize()
