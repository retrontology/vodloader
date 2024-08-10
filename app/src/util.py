from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
import os
from pathlib import Path

DEFAULT_DOWNLOAD_DIR = 'videos'

async def get_live(twitch: Twitch, user_id: int|str):
    if type(user_id) is int:
        user_id = f'{user_id}'
    data = await first(twitch.get_streams(user_id=user_id))
    if data == None:
        return False
    elif data.type == 'live':
        return True
    else:
        return False

def get_download_dir() -> Path:
    if 'DOWNLOAD_DIR' not in os.environ:
        os.environ['DOWNLOAD_DIR'] = DEFAULT_DOWNLOAD_DIR
    download_dir = Path(os.environ['DOWNLOAD_DIR'])
    return download_dir