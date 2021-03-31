from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink
import vodloader_config
import os
import _thread
import time


class vod_watcher(object):

    def __init__(self, streamer, twitch, hook, download_dir, quality='best'):
        self.streamer = streamer
        self.quality = quality
        self.download_dir = download_dir
        self.twitch = twitch
        self.hook = hook
        self.user_id = self.get_user_id()
        self.check_live()
        self.webhook_subscribe()


    def __del__(self):
        self.webhook_unsubscribe()


    def callback_stream_changed(self, uuid, data):
        if data['type'] == 'live':
            if not self.live:
                name = data['started_at'] + '.ts'
                path = os.path.join(self.download_dir, name)
                _thread.start_new_thread(self.download_stream, (path, ))
            self.live = True
        else:
            self.live = False


    def check_live(self):
        if self.twitch.get_streams(user_id=self.user_id)['data'][0]['type'] == 'live':
            self.live = True
        else:
            self.live = False
        return self.live


    def webhook_unsubscribe(self):
        if self.webhook_uuid:
            self.hook.unsubscribe(self.webhook_uuid)


    def webhook_subscribe(self, retry=3):
        for i in range(retry):
            success, uuid = self.hook.subscribe_stream_changed(self.user_id, self.callback_stream_changed)
            if success:
                self.webhook_uuid = uuid
                break
        return success


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


def load_config(filename):
    config = vodloader_config.vodloader_config(filename)
    if not config['download']['directory'] or config['download']['directory'] == "":
        config['download']['directory'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')
    return config


def setup_twitch(client_id, client_secret):
    twitch = Twitch(client_id, client_secret)
    twitch.authenticate_app([])
    return twitch


def setup_webhook(host, client_id, port, twitch):
    hook = TwitchWebHook(host, client_id, port)
    hook.authenticate(twitch)
    hook.start()
    return hook


def main():
    config = load_config('config.yaml')
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['webhook']['host'], config['twitch']['client_id'], config['webhook']['port'], twitch)
    vodw = vod_watcher(config['twitch']['streamer'], twitch, hook, config['download']['directory'])
    while True:
        time.sleep(600)


if __name__ == '__main__':
    main()