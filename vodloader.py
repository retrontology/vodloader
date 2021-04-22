from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from twitchAPI.types import VideoType
import os
from time import sleep
from threading import Thread
import pickle
import logging
from vodloader_video import vodloader_video
from vodloader_status import vodloader_status
from vodloader_chapters import vodloader_chapters
import pytz

class vodloader(object):

    def __init__(self, channel, twitch, webhook, twitch_config, yt_json, download_dir, keep=False, upload=True, tz=pytz.timezone("America/Chicago")):
        self.end = False
        self.channel = channel
        self.logger = logging.getLogger(f'vodloader.{self.channel}')
        self.logger.info(f'Setting up vodloader for {self.channel}')
        self.tz = tz
        self.download_dir = download_dir
        self.keep = keep
        self.twitch = twitch
        self.webhook = webhook
        self.upload = upload
        if self.upload:
            self.upload_queue = []
            self.youtube = self.setup_youtube(yt_json)
            self.youtube_args = twitch_config['youtube_param']
            self.upload_process = Thread(target=self.upload_queue_loop, args=())
            self.upload_process.start()
        else:
            self.youtube = None
            self.youtube_args = None
        self.user_id = self.get_user_id()
        self.status = vodloader_status(self.user_id)
        self.get_live()
        self.webhook_subscribe()
        if 'chapters' in twitch_config and twitch_config['chapters'] != "":
            self.chapters_type = twitch_config['chapters']
        else:
            self.chapters_type = False
        if 'quality' in twitch_config and twitch_config['quality'] != "":
            self.quality = twitch_config['quality']
        else:
            self.quality = 'best'
        if 'backlog' in twitch_config and twitch_config['backlog']:
            self.backlog = twitch_config['backlog']
        else:
            self.backlog = False
        if self.backlog:
            self.backlog_process = Thread(target=self.backlog_buffload, args=())
            self.backlog_process.start()

    def setup_youtube(self, jsonfile):
        self.logger.info(f'Building YouTube flow for {self.channel}')
        api_name = 'youtube'
        api_version = 'v3'
        scopes = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube']
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
                url = 'https://www.twitch.tv/' + self.channel
                self.livestream = vodloader_video(self, url, data, backlog=False, quality=self.quality)
            else:
                self.live = True
                if self.livestream.chapters.get_current_game() != data["game_name"]:
                    self.logger.info(f'{self.channel} has changed game to {data["game_name"]}')
                if self.livestream.chapters.get_current_title() != data["title"]:
                    self.logger.info(f'{self.channel} has changed their title to {data["title"]}')
                self.livestream.chapters.append(data['game_name'], data['title'])
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

    def get_user_id(self):
        user_info = self.twitch.get_users(logins=[self.channel])
        return user_info['data'][0]['id']

    def upload_queue_loop(self):
        while True:
            if len(self.upload_queue) > 0:
                self.upload_queue[0].start()
                self.upload_queue[0].join()
                del self.upload_queue[0]
            else: sleep(15)
            if self.end: break

    def queue_upload(self, path, body, vid_id, keep=False, chunk_size=4194304, retry=3):
        thread = Thread(target=self.upload_video, args=(path, body, vid_id, keep))
        self.upload_queue.append(thread)

    def upload_video(self, path, body, id, keep=False, chunk_size=4194304, retry=3):
        self.logger.info(f'Uploading file {path} to YouTube account for {self.channel}')
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
            if self.youtube_args['playlistId']:
                self.add_video_to_playlist(response["id"], self.youtube_args['playlistId'])
            self.status[id] = 'uploaded'
            if not keep: os.remove(path)
        else:
            self.logger.info(f'Could not parse a video ID from uploading {path}')

    def add_video_to_playlist(self, video_id, playlist_id, pos=0):
        request = self.youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "position": pos,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        try:
            r = request.execute()
            self.logger.debug(r)
            return r
        except Exception as e:
            self.logger.error(e)

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
            v = vodloader_video(self, video['url'], video, backlog=True, quality=self.quality)
            v.thread.join()