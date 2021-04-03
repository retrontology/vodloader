from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink
from functools import partial
from googleapiclient.discovery import build
#from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
import httplib2
import sys
# import google_auth_oauthlib
import os
from vodloader_config import vodloader_config
from webhook_ssl import proxy_request_handler
import _thread
import time
import http.server
import ssl
import datetime


class vodloader(object):

    def __init__(self, streamer, twitch, webhook, youtube, youtube_args, download_dir, quality='best'):
        self.streamer = streamer
        self.quality = quality
        self.download_dir = download_dir
        self.twitch = twitch
        self.webhook = webhook
        self.youtube = youtube
        self.youtube_args = youtube_args
        self.user_id = self.get_user_id()
        self.get_live()
        self.webhook_uuid = ''
        self.webhook_subscribe()


    def __del__(self):
        self.webhook_unsubscribe()


    def callback_stream_changed(self, uuid, data):
        if data['type'] == 'live':
            if not self.live:
                self.live = True
                filename = data['started_at'] + '.ts'
                path = os.path.join(self.download_dir, filename)
                date = datetime.datetime.strptime(data['started_at'], '%Y-%m-%dT%H:%M:%SZ')
                name = self.streamer + " " + date.strftime("%m/%d/%Y") + " VOD"
                body = self.get_youtube_body(name)
                _thread.start_new_thread(self.stream_buffload, (path, body, ))
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


    def get_stream(self):
        url = 'https://www.twitch.tv/' + self.streamer
        return streamlink.streams(url)[self.quality]


    def get_user_id(self):
        user_info = self.twitch.get_users(logins=[self.streamer])
        return user_info['data'][0]['id']


    def get_youtube_body(self, title):
        body = {
            'snippet': {
                'title': title,
                'description': self.youtube_args['description'],
                'tags': self.youtube_args['tags'],
                'categoryId': self.youtube_args['categoryId']
        },
            'status': {
                'privacyStatus': self.youtube_args['privacy'],
                'selfDeclaredMadeForKids': False
            }
        }
        return body


    def stream_download(self, path, chunk_size=8192):
        stream = self.get_stream().open()
        with open(path, 'rb') as f:
            data = stream.read(chunk_size)
            while data:
                try:
                    f.write(data)
                except OSError as err:
                    print(err)
                    break
                data = stream.read(chunk_size)
        stream.close()
    

    def stream_upload(self, path, body, chunk_size=8192):
        media = MediaFileUpload(path)
        upload = self.youtube.videos().insert(",".join(body.keys()), body=body, media_body=media)
        upload.execute()

    
    def stream_buffload(self, path, body, chunk_size=8192):
        self.stream_download(path, chunk_size=chunk_size)
        self.stream_upload(path, body, chunk_size=chunk_size)
        os.remove(path)


    # def stream_to_youtube(self, body, chunk_size=8192):
    #     stream = self.get_stream().open()
    #     media = MediaIoBaseUpload(stream, mimetype='video/mp2t', chunksize=chunk_size, resumable=True)
    #     upload = self.youtube.videos().insert(",".join(body.keys()), body=body, media_body=media)
    #     upload.execute()


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


def setup_youtube(jsonfile):
    MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

   %s

with information from the API Console
https://console.developers.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__), jsonfile))
    storage = Storage("%s-oauth2.json" % sys.argv[0])
    creds = storage.get()
    if creds is None or creds.invalid:
        flow = flow_from_clientsecrets(jsonfile, scope="https://www.googleapis.com/auth/youtube.upload", message=MISSING_CLIENT_SECRETS_MESSAGE)
        creds = run_flow(flow, storage)
    return build('youtube', 'v3', http=creds.authorize(httplib2.Http()))


def main():
    config = load_config('config.yaml')
    youtube = setup_youtube(config['youtube']['json'])
    ssl_httpd = setup_ssl_reverse_proxy(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['webhook']['port'], config['twitch']['webhook']['ssl_cert'])
    twitch = setup_twitch(config['twitch']['client_id'], config['twitch']['client_secret'])
    hook = setup_webhook(config['twitch']['webhook']['host'], config['twitch']['webhook']['ssl_port'], config['twitch']['client_id'], config['twitch']['webhook']['port'], twitch)
    vodl = vodloader(config['twitch']['streamer'], twitch, hook, youtube, config['youtube']['arguments'], config['download']['directory'])
    try:
        while True:
            time.sleep(600)
    except:
        vodl.webhook_unsubscribe()
        hook.stop()
        ssl_httpd.shutdown()
        ssl_httpd.socket.close()


if __name__ == '__main__':
    main()