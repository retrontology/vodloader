from twitchAPI.twitch import Twitch
from twitchAPI.webhook import TwitchWebHook
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.types import AuthScope
import streamlink
from functools import partial
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
import sys
import os
from vodloader_config import vodloader_config
from webhook_ssl import proxy_request_handler
import _thread
import time
import http.server
import ssl
import datetime
import pickle


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


    def stream_download(self, path, chunk_size=1048576):
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
    

    def stream_upload(self, path, body, chunk_size=1048576):
        media = MediaFileUpload(path, mimetype='video/mpegts', chunksize=chunk_size, resumable=True)
        upload = self.youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
        try:
            upload.execute()
        except HttpError as e:
            print(e.resp)
            print(e.content)


    
    def stream_buffload(self, path, body, chunk_size=1048576):
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
    api_name = 'youtube'
    api_version = 'v3'
    scopes = ['https://www.googleapis.com/auth/youtube.upload']
    pickle_file = os.path.join(os.path.dirname(__file__), f'token_{api_name}_{api_version}.pickle')
    creds = None
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(jsonfile, scopes)
            creds = flow.run_console()
        with open(pickle_file, 'wb') as token:
            pickle.dump(creds, token)
    return build(api_name, api_version, credentials=creds)


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