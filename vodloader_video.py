from vodloader_chapters import vodloader_chapters
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from threading import Thread
import logging
import os
import datetime
import streamlink
import requests
import json


class vodloader_video(object):

    def __init__(self, parent, url, twitch_data, backlog=False, quality='best', part=1):
        self.parent = parent
        self.logger = logging.getLogger(f'vodloader.{self.parent.channel}.video')
        self.part = part
        self.backlog = backlog
        self.quality = quality
        self.passed = False
        self.upload = self.parent.upload
        self.keep = self.parent.keep
        self.twitch_data = twitch_data
        self.id = twitch_data['id']
        if backlog: self.start_absolute = twitch_data['created_at']
        else: self.start_absolute = twitch_data['started_at']
        self.start_absolute = self.parent.tz.localize(datetime.datetime.strptime(self.start_absolute, '%Y-%m-%dT%H:%M:%SZ'))
        self.start = datetime.datetime.now()
        self.download_url = url
        name = self.id
        if self.part > 1:
            name += f'.p{self.part}'
            self.id += f'p{self.part}'
        name += '.ts'
        self.path = os.path.join(self.parent.download_dir, name)
        self.chapters = self.chapters_init(twitch_data)
        self.thread = Thread(target=self.buffload_stream, args=())
        self.thread.start()

    def chapters_init(self, twitch_data):
        if self.backlog:
            chapters = None
        else:
            game = twitch_data['game_name']
            title = twitch_data['title']
            chapters = vodloader_chapters(game, title)
        return chapters

    def __del__(self):
        pass
    
    def get_stream(self, url, quality):
        return streamlink.streams(url)[quality]

    def buffload_stream(self):
        if not self.id in self.parent.status:
            self.download_stream()
            self.parent.status[self.id] = 'downloaded'
        if self.upload and self.parent.status[self.id] != 'uploaded':
            self.upload_stream()

    def download_stream(self, chunk_size=8192, max_length=60*(60*12-15)):
        self.logger.info(f'Downloading stream from {self.download_url} to {self.path}')
        stream = self.get_stream(self.download_url, self.quality).open()
        with open(self.path, 'wb') as f:
            data = stream.read(chunk_size)
            while data:
                try:
                    f.write(data)
                    data = stream.read(chunk_size)
                except OSError as err:
                    self.logger.error(err)
                    break
                if (datetime.datetime.now() - self.start).seconds > max_length-15 and not self.passed:
                    self.passed = True
                    self.logger.info(f'Max length of {max_length} seconds has been exceeded for {self.path}, continuing download in part {self.part+1}')
                    self.parent.oldstream = self
                    self.parent.livestream = vodloader_video(self.parent, self.download_url, self.twitch_data, backlog=self.backlog, quality=self.quality, part=self.part+1)
                if (datetime.datetime.now() - self.start).seconds > max_length:
                    stream.close()
        stream.close()
        self.logger.info(f'Finished downloading stream from {self.download_url}')

    def upload_stream(self, chunk_size=4194304, retry=3):
        self.parent.queue_upload(self.path, self.get_youtube_body(self.parent.chapters_type), self.id, keep=self.keep)
    
    def get_youtube_body(self, chapters=False):
        body = {
            'snippet': {
                'title': self.get_formatted_string(self.parent.youtube_args['title'], self.start_absolute),
                'description': self.get_formatted_string(self.parent.youtube_args['description'], self.start_absolute),
                'tags': []
        },
            'status': {
                'selfDeclaredMadeForKids': False
            }
        }
        if 'tags' in self.parent.youtube_args: body['snippet']['tags'] = self.parent.youtube_args['tags']
        if 'categoryId' in self.parent.youtube_args: body['snippet']['categoryId'] = self.parent.youtube_args['categoryId']
        if 'privacy' in self.parent.youtube_args: body['status']['privacyStatus'] = self.parent.youtube_args['privacy']
        if not self.backlog:
            body['snippet']['tags'] += self.chapters.get_games()
            if chapters:
                if chapters.lower() == 'games' and self.chapters.get_game_chapters():
                    body['snippet']['description'] += f'\n\n\n\n{self.chapters.get_game_chapters()}'
                if chapters.lower() == 'titles' and self.chapters.get_title_chapters():
                    body['snippet']['description'] += f'\n\n\n\n{self.chapters.get_title_chapters()}'
        if self.part > 1:
            body['snippet']['title'] = f'{body["snippet"]["title"]} Part {self.part}'
        return body

    def get_formatted_string(self, input, date):
        output = input.replace('%C', self.parent.channel)
        output = output.replace('%i', self.id)
        output = output.replace('%g', self.chapters.get_first_game())
        output = output.replace('%G', self.chapters.get_current_game())
        output = output.replace('%t', self.chapters.get_first_title())
        output = output.replace('%t', self.chapters.get_current_title())
        output = date.strftime(output)
        return output
    
    def get_stream_markers(self, retry=3):
        url = f'https://api.twitch.tv/kraken/videos/{self.id}/markers?api_version=5&client_id={self.parent.twitch.app_id}'
        for i in range(retry):
            r = requests.get(url)
            if r.status_code == 200:
                return json.loads(r.content)
        return None