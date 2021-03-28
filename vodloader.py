from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink


def callback_stream_changed(uuid, data):
    print('UUID: ' + uuid)
    print(data)


clientID = ":)"
clientSecret = ":)"
users = ['rlly']
host = ":)"
port = 42069


twitch = Twitch(clientID, clientSecret)
twitch.authenticate_app([])
user_info = twitch.get_users(logins=users)
user_id = user_info['data'][0]['id']
hook = TwitchWebHook(host, clientID, port)
hook.start()
success, uuid = hook.subscribe_stream_changed(user_id, callback_stream_changed)