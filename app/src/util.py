from twitchAPI.twitch import Twitch
from twitchAPI.helper import first

async def get_live(twitch: Twitch, user_id):
    data = await first(twitch.get_streams(user_id=user_id))
    if data == None:
        return False
    elif data['type'] == 'live':
        return True
    else:
        return False
