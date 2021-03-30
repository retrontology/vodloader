from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink
import vodloader_config


class vod_watcher(object):

    def __init__(self, streamer, twitch, hook, quality='best'):
        self.streamer = streamer
        self.quality = quality
        self.twitch = twitch
        self.hook = hook
        self.user_id = self.get_user_id()
        self.webhook_setup()


    def callback_stream_changed(self, uuid, data):
        print('UUID: ' + uuid)
        print(data)


    def webhook_setup(self):
        success, uuid = self.hook.subscribe_stream_changed(self.user_id, self.callback_stream_changed)


    def get_stream(self, quality='best'):
        url = 'https://www.twitch.tv/' + self.streamer
        return streamlink.streams(url)[quality]


    def get_user_id(self):
        user_info = self.twitch.get_users(logins=[self.streamer])
        return user_info['data'][0]['id']


    def download_stream(self, path, chunk_size=8192):
        stream = self.get_stream().open()
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


def main():
    twitch = Twitch(clientID, clientSecret)
    twitch.authenticate_app([])
    hook = TwitchWebHook(host, twitch_client_id, port)
    hook.authenticate(twitch)
    hook.start()
    rlly = vod_watcher('rlly', twitch, hook)