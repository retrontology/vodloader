from twitchAPI.types import VideoType
from time import sleep
from tzlocal import get_localzone
from threading import Thread
import os
import logging
from vodloader_video import vodloader_video
from vodloader_status import vodloader_status
import pytz
import datetime


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
        self.sync_status()
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
    
    def sync_status(self):
        ids = []
        for video in self.get_channel_videos():
            if video['tvid']:
                if video['part'] and video['part'] > 1:
                    ids.append(f'{video["tvid"]}p{video["part"]}')
                else:
                    ids.append(str(video['tvid']))
        for id in self.status.copy():
            if not id in ids and self.status[id] == True:
                self.status.pop(id)
        for id in ids:
            self.status[id] = True
        self.status.save()

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