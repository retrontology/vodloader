from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink
from functools import partial
#from google.oauth2 import service_account
from vodloader_config import vodloader_config
from webhook_ssl import proxy_request_handler
import os
import _thread
import time
import json
import http.server
import ssl


class vodloader(object):

    def __init__(self, streamer, twitch, webhook, download_dir, quality='best'):
        self.streamer = streamer
        self.quality = quality
        self.download_dir = download_dir
        self.twitch = twitch
        self.webhook = webhook
        self.user_id = self.get_user_id()
        self.get_live()
        self.webhook_uuid = ''
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


    def get_live(self):
        data = self.twitch.get_streams(user_id=self.user_id)
        if not data['data']:
            self.live = False
        elif data['data'][0]['type'] == 'live':
            self.live = True
        else:
            self.live = False
        return self.live


    def webhook_unsubscribe(self):
        if self.webhook_uuid:
            success = self.webhook.unsubscribe(self.webhook_uuid)
            if success: self.webhook_uuid = ''
            return success


    def webhook_subscribe(self):
        success, uuid = self.webhook.subscribe_stream_changed(self.user_id, self.callback_stream_changed)
        if success: self.webhook_uuid = uuid
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
    config = vodloader_config(filename)
    if not config['download']['directory'] or config['download']['directory'] == "":
        config['download']['directory'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')
    return config


def setup_twitch(client_id, client_secret):
    twitch = Twitch(client_id, client_secret)
    twitch.authenticate_app([])
    return twitch


def setup_ssl_reverse_proxy(host, ssl_port, http_port, certfile):
    handler = partial(proxy_request_handler, http_port)
    httpd = http.server.HTTPServer((host, ssl_port), handler)
    httpd.socket = ssl.wrap_socket(httpd.socket, certfile=certfile, server_side=True)
    _thread.start_new_thread(httpd.serve_forever, ())
    return httpd


def setup_webhook(host, ssl_port, client_id, port, twitch):
    hook = TwitchWebHook('https://' + host + ":" + str(ssl_port), client_id, port)
    hook.authenticate(twitch) 
    hook.start()
    return hook


def setup_youtube(config):
    jdata = {}
    jdata["installed"] = {}
    jdata["installed"]["client_id"] = config['youtube']['client_id']
    jdata["installed"]["client_secret"] = config['youtube']['client_secret']
    jdata["installed"]["auth_uri"] = config['youtube']['auth_uri']
    jdata["installed"]["token_uri"] = config['youtube']['token_uri']
    jdata = json.dumps(jdata)


def main():
    config = load_config('config.yaml')
    ssl_httpd = setup_ssl_reverse_proxy(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['webhook']['port'], config['twitch']['webhook']['ssl_cert'])
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['client_id'], config['twitch']['webhook']['port'], twitch)
    vodl = vodloader(config['twitch']['streamer'], twitch, hook, config['download']['directory'])
    try:
        while True:
            time.sleep(600)
    except:
        vodl.webhook_unsubscribe()
        hook.stop()
        ssl_httpd.shutdown()


if __name__ == '__main__':
    main()