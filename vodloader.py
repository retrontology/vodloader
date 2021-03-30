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


def get_stream(streamer, quality='best'):
    url = 'https://www.twitch.tv/' + streamer
    return streamlink.streams(url)[quality]


def download_stream(streamer, path, chunk_size=8192):
    stream = get_stream(streamer).open()
    with open(path, 'wb') as f:
        data = stream.read(chunk_size)
        while data:
            try:
                f.write(data)
            except OSError as err:
                print(err)
                break
            data = stream.read(chunk_size)
    stream.close()


clientID = ":)"
clientSecret = ":)"
users = ['rlly']
host = ":)"
port = 42069

download_stream('rlly', '/mnt/media/test.ts')