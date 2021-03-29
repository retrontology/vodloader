from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink


def main():
    webhook_setup()


def callback_stream_changed(uuid, data):
    print('UUID: ' + uuid)
    print(data)


def webhook_setup():
    twitch = Twitch(clientID, clientSecret)
    twitch.authenticate_app([])
    user_info = twitch.get_users(logins=users)
    user_id = user_info['data'][0]['id']
    hook = TwitchWebHook(host, clientID, port)
    hook.start()
    success, uuid = hook.subscribe_stream_changed(user_id, callback_stream_changed)


def get_stream(streamer):
    url = 'https://www.twitch.tv/' + streamer
    return streamlink.streams(url)['best']


clientID = ":)"
clientSecret = ":)"
users = ['rlly']
host = ":)"
port = 42069

path = '/mnt/media/test'
stream = get_stream('rlly')
with open(path+".part", 'wb') as f:
    for i in range(1000000):
        f.write(stream.read(1024))
stream.close()