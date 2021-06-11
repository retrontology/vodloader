from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from twitchAPI.types import VideoType
import os
from time import sleep
from tzlocal import get_localzone
from threading import Thread
import pickle
import logging
from vodloader_video import vodloader_video
from vodloader_status import vodloader_status
from vodloader_chapters import vodloader_chapters
import pytz
import datetime
import json

class vodloader(object):

    def __init__(self, channel, twitch, webhook, twitch_config, yt_json, download_dir, keep=False, upload=True, quota_pause=True, tz=pytz.timezone("America/Chicago")):
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
        self.quota_pause = quota_pause
        self.pause = False
        self.youtube_args = twitch_config['youtube_param']
        if self.upload:
            self.upload_queue = []
            self.youtube = self.setup_youtube(yt_json)
            self.upload_process = Thread(target=self.upload_queue_loop, args=(), daemon=True)
            self.upload_process.start()
        else:
            self.youtube = None
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
            self.backlog_process = Thread(target=self.backlog_buffload, args=(), daemon=True)
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
                try:
                    self.upload_video(*self.upload_queue[0])
                    del self.upload_queue[0]
                except YouTubeOverQuota as e:
                    self.wait_for_quota()
            else: sleep(1)
            if self.end: break

    def upload_video(self, path, body, id, keep=False, chunk_size=4194304, retry=3):
        self.logger.info(f'Uploading file {path} to YouTube account for {self.channel}')
        uploaded = False
        attempts = 0
        response = None
        while uploaded == False:
            media = MediaFileUpload(path, mimetype='video/mpegts', chunksize=chunk_size, resumable=True)
            upload = self.youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
            try:
                response = upload.execute()
                self.logger.debug(response)
                uploaded = response['status']['uploadStatus'] == 'uploaded'
            except HttpError as e:
                c = json.loads(e.content)
                if c['error']['errors'][0]['domain'] == 'youtube.quota' and c['error']['errors'][0]['reason'] == 'quotaExceeded':
                    raise YouTubeOverQuota
                else:
                    self.logger.error(e.resp)
                    self.logger.error(e.content)
            except BrokenPipeError as e:
                self.logger.error(e)
            if not uploaded:
                attempts += 1
            if attempts >= retry:
                self.logger.error(f'Number of retry attempts exceeded for {path}')
                break
        if response and 'id' in response:
            self.logger.info(f'Finished uploading {path} to https://youtube.com/watch?v={response["id"]}')
            if self.youtube_args['playlistId']:
                self.add_video_to_playlist(response["id"], self.youtube_args['playlistId'])
            self.status[id] = True
            self.status.save()
            if not keep: os.remove(path)
        else:
            self.logger.info(f'Could not parse a video ID from uploading {path}')
    
    def wait_for_quota(self):
        self.pause = True
        now = datetime.datetime.now()
        until = now + datetime.timedelta(days=1)
        until = until - datetime.timedelta(microseconds=until.microsecond, seconds=until.second, minutes=until.minute, hours=until.hour)
        until = pytz.timezone('US/Pacific').localize(until)
        now = get_localzone().localize(now)
        wait = until - now
        if wait.days > 0:
            wait = wait - datetime.timedelta(days=wait.days)
        self.logger.error(f'YouTube upload quota has been exceeded, waiting for reset at Midnight Pacific Time in {wait.seconds} seconds')
        sleep(wait.seconds + 15)
        self.pause = False

    def get_playlist_items(self, playlist_id):
        items = []
        npt = ""
        while True:
            request = self.youtube.playlistItems().list(
                part="snippet",
                maxResults=50,
                pageToken=npt,
                playlistId=playlist_id
            )
            response = request.execute()
            for item in response['items']:
                item['tvid'], item['part'] = self.get_tvid_from_yt_item(item)
                items.append(item)
            if 'nextPageToken' in response:
                npt = response['nextPageToken']
            else:
                break
        return items
    
    def get_channel_items(self):
        request = self.youtube.channels.list(part="contentDetails", mine=True)
        try:
            r = request.execute()
            self.logger.debug(r)
            uploads = r['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        except Exception as e:
            self.logger.error(e)
            return None
        return self.get_playlist_items(uploads)
    
    @staticmethod
    def get_tvid_from_yt_item(item):
        tvid = None
        for tag in item['snippet']['tags']:
            if tag[:5] == 'tvid:':
                tvid = tag[5:]
        if tvid:
            tvid = tvid.split('.p', 1)
            id = int(tvid[0])
            if len(tvid) > 1: part = int(tvid[1])
            else: part = None
            return id, part
        else: return None, None

    def add_video_to_playlist(self, video_id, playlist_id, pos=-1):
        if pos == -1:
            pos = len(self.get_playlist_items(playlist_id))
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
    
    def set_video_playlist_pos(self, video_id, playlist_id, pos):
        request = self.youtube.playlistItems().update(
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

    def sort_playlist(self, playlist_id, reverse=False):
        videos = self.get_playlist_items(playlist_id)
        ordered = videos.copy()
        ordered.sort(reverse=reverse, key=lambda x: (x['tvid'], x['part']))
        i = 0
        while i < len(videos):
            if not videos[i]['id'] == ordered[i]['id']:
                pass
            i+=1

    def get_twitch_videos(self, video_type=VideoType.ARCHIVE):
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
        videos = self.get_twitch_videos()
        videos.sort(reverse=False, key=lambda x: datetime.datetime.strptime((x['created_at']), '%Y-%m-%dT%H:%M:%SZ'))
        datafile = os.path.join(self.download_dir, 'titles.txt')
        for video in videos:
            if self.pause and self.quota_pause:
                self.logger.info('Pausing backlog processing until YouTube quota is refreshed')
                while self.pause:
                    sleep(10)
            self.backlog_video = vodloader_video(self, video['url'], video, backlog=True, quality=self.quality)
            title = f'{self.backlog_video.id}: {self.backlog_video.get_formatted_string(self.youtube_args["title"], self.backlog_video.start_absolute)}\n'
            while self.backlog_video.thread.is_alive():
                self.backlog_video.thread.join()
                sleep(1)
            if not self.upload:
                with open(datafile, 'a') as fl:
                    fl.write(title)

class YouTubeOverQuota(Exception):
    """ called when youtube upload quota is exceeded """
    pass