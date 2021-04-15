from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from twitchAPI.types import VideoType
import os
import _thread
import datetime
import pickle
import logging
from vodloader_streamlink import FixedStreamlink
from vodloader_status import vodloader_status
from vodloader_chapters import vodloader_chapters

class vodloader(object):

    def __init__(self, channel, twitch, webhook, config):
        self.logger = logging.getLogger(f'vodloader.twitch.{channel}')
        self.logger.info(f'Setting up vodloader for {channel}')
        self.config = config
        self.channel = channel
        if 'quality' in self.config['twitch']['channels'][self.channel] and self.config['twitch']['channels'][self.channel]['quality'] != "":
            self.quality = self.config['twitch']['channels'][self.channel]['quality']
        else:
            self.quality = 'best'
        self.chapters = None
        self.download_dir = config['download']['directory']
        self.keep = config['download']['keep']
        self.twitch = twitch
        self.webhook = webhook
        self.upload = config['youtube']['upload']
        if self.upload:
            self.youtube = self.setup_youtube(self.config['youtube']['json'])
            self.youtube_args = self.config['twitch']['channels'][self.channel]['youtube_param']
        else:
            self.youtube = None
            self.youtube_args = None
        self.user_id = self.get_user_id()
        self.status = vodloader_status(self.user_id)
        self.get_live()
        self.webhook_subscribe()
        if 'backlog' in self.config['twitch']['channels'][self.channel] and self.config['twitch']['channels'][self.channel]['backlog']:
            self.backlog = self.config['twitch']['channels'][self.channel]['backlog']
        else:
            self.backlog = False
        if self.backlog:
            _thread.start_new_thread(self.backlog_buffload, ())


    def setup_youtube(self, jsonfile):
        self.logger.info(f'Building YouTube flow for {self.channel}')
        api_name = 'youtube'
        api_version = 'v3'
        scopes = ['https://www.googleapis.com/auth/youtube.upload']
        pickle_dir = os.path.join(os.path.dirname(__file__), 'pickles')
        if not os.path.exists(pickle_dir):
            self.logger.info(f'Creating pickle directory')
            os.mkdir(pickle_dir)
        pickle_file = os.path.join(pickle_dir, f'token_{self.channel}.pickle')
        creds = None
        if os.path.exists(pickle_file):
            with open(pickle_file, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info(f'YouTube credential pickle file for {self.channel} is expired. Attempting to refresh now')
                creds.refresh(Request())
            else:
                print(f'Please log into the YouTube account that will host the vods of {self.channel} below')
                flow = InstalledAppFlow.from_client_secrets_file(jsonfile, scopes)
                creds = flow.run_console()
            with open(pickle_file, 'wb') as token:
                pickle.dump(creds, token)
                self.logger.info(f'YouTube credential pickle file for {self.channel} has been written to {pickle_file}')
        else:
            self.logger.info(f'YouTube credential pickle file for {self.channel} found!')
        return build(api_name, api_version, credentials=creds)


    def __del__(self):
        self.webhook_unsubscribe()


    def callback_stream_changed(self, uuid, data):
        self.logger.info(f'Received webhook callback for {self.channel}')
        if data['type'] == 'live':
            if not self.live:
                self.live = True
                self.logger.info(f'{self.channel} has gone live!')
                self.chapters = vodloader_chapters(data['game_name'], data['title'])
                url = 'https://www.twitch.tv/' + self.channel
                filename = f'{self.channel}_{data["started_at"]}.ts'
                path = os.path.join(self.download_dir, filename)
                date = datetime.datetime.strptime(data['started_at'], '%Y-%m-%dT%H:%M:%SZ')
                name = f'{self.channel} {date.strftime("%m/%d/%Y")} VOD'
                video_id = data["id"]
                _thread.start_new_thread(self.stream_buffload, (url, path, name, video_id, ))
            else:
                self.live = True
                if self.channel.get_current_game != data["game_name"]:
                    self.logger.info(f'{self.channel} has changed game to {data["game_name"]}')
                if self.channel.get_current_game != data["title"]:
                    self.logger.info(f'{self.channel} has changed their title to {data["title"]}')
                self.chapters.append(data['game_name'], data['title'])
        else:
            self.live = False
            self.logger.info(f'{self.channel} has gone offline')


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
            if success:
                self.webhook_uuid = ''
                self.logger.info(f'Unsubscribed from webhook for {self.channel}')
            return success


    def webhook_subscribe(self):
        success, uuid = self.webhook.subscribe_stream_changed(self.user_id, self.callback_stream_changed)
        if success:
            self.webhook_uuid = uuid
            self.logger.info(f'Subscribed to webhook for {self.channel}')
        else:
            self.webhook_uuid = None
        return success


    def get_stream(self, url, quality):
        fs = FixedStreamlink()
        ft = fs.resolve_url(url)
        ft.bind(fs, 'FixedTwitch')
        return fs.streams(url)[quality]


    def get_user_id(self):
        user_info = self.twitch.get_users(logins=[self.channel])
        return user_info['data'][0]['id']


    def get_youtube_body(self, title, chapters=False, backlog=False):
        body = {
            'snippet': {
                'title': title,
                'description': '',
                'tags': []
        },
            'status': {
                'selfDeclaredMadeForKids': False
            }
        }
        if 'description' in self.youtube_args: body['snippet']['description'] = self.youtube_args['description']
        if 'tags' in self.youtube_args: body['snippet']['tags'] = self.youtube_args['tags']
        if 'categoryId' in self.youtube_args: body['snippet']['categoryId'] = self.youtube_args['categoryId']
        if 'playlistId' in self.youtube_args: body['snippet']['playlistId'] = self.youtube_args['playlistId']
        if 'privacy' in self.youtube_args: body['status']['privacyStatus'] = self.youtube_args['privacy']
        if not backlog:
            body['snippet']['tags'] += self.chapters.get_games()
            if chapters:
                if chapters.lower() == 'games':
                    body['snippet']['description'] += f'\n\n\n\n{self.chapters.get_game_chapters()}'
                if chapters.lower() == 'titles':
                    body['snippet']['description'] += f'\n\n\n\n{self.chapters.get_title_chapters()}'
        return body


    def stream_download(self, url, path, chunk_size=8192):
        self.logger.info(f'Downloading stream from {url} to {path}')
        stream = self.get_stream(url, self.quality).open()
        with open(path, 'wb') as f:
            data = stream.read(chunk_size)
            while data:
                try:
                    f.write(data)
                    data = stream.read(chunk_size)
                except OSError as err:
                    self.logger.error(err)
                    break
        stream.close()
        self.logger.info(f'Finished downloading stream from {self.channel}')
    

    def stream_upload(self, path, title, backlog = False, chunk_size=4194304, retry=3):
        self.logger.info(f'Uploading file {path} to YouTube account for {self.channel}')
        body = self.get_youtube_body(title, self.config['twitch']['channels'][self.channel]['chapters'], backlog=backlog)
        uploaded = False
        attempts = 0
        while uploaded == False:
            media = MediaFileUpload(path, mimetype='video/mpegts', chunksize=chunk_size, resumable=True)
            upload = self.youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
            try:
                response = upload.execute()
            except HttpError as e:
                self.logger.error(e.resp)
                self.logger.error(e.content)
            self.logger.debug(response)
            uploaded = response['status']['uploadStatus'] == 'uploaded'
            if not uploaded:
                attempts += 1
            if attempts >= retry:
                self.logger.error(f'Number of retry attempt exceeded for {path}')
                break
        if 'id' in response:
            self.logger.info(f'Finished uploading {path} to https://youtube.com/watch?v={response["id"]}')
        else:
            self.logger.info(f'Could not parse a video ID from uploading {path}')

    
    def stream_buffload(self, url, path, title, video_id, backlog=False):
        if not video_id in self.status:
            self.stream_download(url, path)
            self.status[video_id] = 'downloaded'
        if self.upload and self.status[video_id] != 'uploaded':
            self.stream_upload(path, title, backlog=backlog)
            self.status[video_id] = 'uploaded'
        if os.path.exists(path) and not self.keep:
            os.remove(path)


    def get_channel_videos(self, video_type=VideoType.ARCHIVE):
        cursor = None
        videos = []
        while True:
            data = self.twitch.get_videos(user_id=self.user_id, first=100, after=cursor)
            for video in data['data']:
                if video['type'] == video_type:
                    videos.append(video)
            if not 'cursor' in data['pagination']:
                break
            else:
                cursor = data['pagination']['cursor']
        return videos
    

    def backlog_buffload(self):
        videos = self.get_channel_videos()
        videos.sort(reverse=False, key=lambda x: x['id'])
        for video in videos:
            filename = f'{self.channel}_{video["created_at"]}.ts'
            date = datetime.datetime.strptime(video['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            name = f'{self.channel} {date.strftime("%m/%d/%Y")} VOD'
            path = os.path.join(self.download_dir, filename)
            video_id = video['id']
            self.stream_buffload(video['url'], path, name, video_id, True,)