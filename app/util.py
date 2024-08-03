from twitchAPI.twitch import Twitch

async def get_live(twitch: Twitch, user_id):
    data = await twitch.get_streams(user_id=user_id)
    if not data['data']:
        return False
    elif data['data'][0]['type'] == 'live':
        return True
    else:
        return False
