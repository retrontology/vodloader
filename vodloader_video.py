from vodloader_chapters import vodloader_chapters
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from threading import Thread
from math import floor
import logging
import os
import datetime
import streamlink
import requests
import json
import pytz


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
        self.start_absolute = pytz.timezone('UTC').localize(datetime.datetime.strptime(self.start_absolute, '%Y-%m-%dT%H:%M:%SZ'))
        self.start_absolute = self.start_absolute.astimezone(self.parent.tz)
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
            game = ''
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

    def download_stream(self, chunk_size=8192, max_length=60*(60*12-15), retry=10):
        self.logger.info(f'Downloading stream from {self.download_url} to {self.path}')
        stream = self.get_stream(self.download_url, self.quality)
        if self.part > 1 and self.backlog:
            stream.start_offset = (self.part - 1) * (max_length - 60 * 10 * (self.part - 1))
        buff = stream.open()
        if self.backlog:
            seq_limit = floor(max_length/10) * self.part
        error = 0
        with open(self.path, 'wb') as f:
            data = buff.read(chunk_size)
            while data and error < retry:
                try:
                    f.write(data)
                    data = buff.read(chunk_size)
                except OSError as err:
                    self.logger.error(err)
                    error += 1
                if self.backlog:
                    should_pass = buff.worker.playlist_sequence > (seq_limit - 2)
                    should_close = buff.worker.playlist_sequence > seq_limit
                else:
                    should_pass = (datetime.datetime.now() - self.start).seconds > (max_length-15)
                    should_close = (datetime.datetime.now() - self.start).seconds > max_length
                if should_pass and not self.passed:
                    self.passed = True
                    self.logger.info(f'Max length of {max_length} seconds has been exceeded for {self.path}, continuing download in part {self.part+1}')
                    twitch_data = self.twitch_data.copy()
                    twitch_data['game_name'] = self.chapters.get_current_game()
                    twitch_data['title'] = self.chapters.get_current_title()
                    if self.backlog:
                        self.parent.backlog_video = vodloader_video(self.parent, self.download_url, twitch_data, backlog=self.backlog, quality=self.quality, part=self.part+1)
                    else:
                        self.parent.livestream = vodloader_video(self.parent, self.download_url, twitch_data, backlog=self.backlog, quality=self.quality, part=self.part+1)
                if should_close:
                    buff.close()
                    break
        buff.close()
        self.logger.info(f'Finished downloading stream from {self.download_url}')

    def upload_stream(self, chunk_size=4194304, retry=3):
        self.parent.upload_queue.append((self.path, self.get_youtube_body(self.parent.chapters_type), self.id, self.keep))
    
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


