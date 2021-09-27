from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from time import sleep
from threading import Thread
from tzlocal import get_localzone
import pytz
import os
import pickle
import json
import datetime
import logging


class youtube_uploader():

    def __init__(self, parent, jsonfile, youtube_args, sort=True):
        self.parent = parent
        self.logger = logging.getLogger(f'vodloader.{self.parent.channel}.uploader')
        self.end = False
        self.pause = False
        self.sort = sort
        self.jsonfile = jsonfile
        self.youtube_args = youtube_args
        self.youtube = self.setup_youtube(jsonfile)
        self.queue = []
        self.upload_process = Thread(target=self.upload_loop, args=(), daemon=True)
        self.upload_process.start()

    def stop(self):
        self.end = True

    def setup_youtube(self, jsonfile, scopes=['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube']):
        self.logger.info(f'Building YouTube flow for {self.parent.channel}')
        api_name='youtube'
        api_version = 'v3'
        pickle_dir = os.path.join(os.path.dirname(__file__), 'pickles')
        if not os.path.exists(pickle_dir):
            self.logger.info(f'Creating pickle directory')
            os.mkdir(pickle_dir)
        pickle_file = os.path.join(pickle_dir, f'token_{self.parent.channel}.pickle')
        creds = None
        if os.path.exists(pickle_file):
            with open(pickle_file, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self.logger.info(f'YouTube credential pickle file for {self.parent.channel} is expired. Attempting to refresh now')
                creds.refresh(Request())
            else:
                print(f'Please log into the YouTube account that will host the vods of {self.parent.channel} below')
                flow = InstalledAppFlow.from_client_secrets_file(jsonfile, scopes)
                creds = flow.run_console()
            with open(pickle_file, 'wb') as token:
                pickle.dump(creds, token)
                self.logger.info(f'YouTube credential pickle file for {self.parent.channel} has been written to {pickle_file}')
        else:
            self.logger.info(f'YouTube credential pickle file for {self.parent.channel} found!')
        return build(api_name, api_version, credentials=creds)

    def upload_loop(self):
        while True:
            if len(self.queue) > 0:
                try:
                    self.upload_video(*self.queue[0])
                    del self.queue[0]
                except YouTubeOverQuota as e:
                    self.wait_for_quota()
            else: sleep(1)
            if self.end: break

    def upload_video(self, path, body, id, keep=False, chunk_size=4194304, retry=3):
        self.logger.info(f'Uploading file {path} to YouTube account for {self.parent.channel}')
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
                self.check_over_quota(e)
            except (BrokenPipeError, ConnectionResetError) as e:
                self.logger.error(e)
            if not uploaded:
                attempts += 1
            if attempts >= retry:
                self.logger.error(f'Number of retry attempts exceeded for {path}')
                break
        if response and response['status']['uploadStatus'] == 'uploaded':
            self.logger.info(f'Finished uploading {path} to https://youtube.com/watch?v={response["id"]}')
            if self.youtube_args['playlistId']:
                if self.sort:
                    response['tvid'], response['part'] = self.get_tvid_from_yt_video(response)
                    response['timestamp'] = self.get_timestamp_from_yt_video(response)
                    self.insert_into_playlist(response, self.youtube_args['playlistId'])
                else:
                    self.add_video_to_playlist(response["id"], self.youtube_args['playlistId'], pos=0)
            self.parent.status[id] = True
            self.parent.status.save()
            if not keep: 
                sleep(1)
                os.remove(path)
        else:
            self.logger.info(f'Could not upload {path}')
    
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
        i = 1
        while True:
            request = self.youtube.playlistItems().list(
                part="snippet",
                maxResults=50,
                pageToken=npt,
                playlistId=playlist_id
            )
            try:
                response = request.execute()
            except HttpError as e:
                self.check_over_quota(e)
            self.logger.debug(f'Retrieved page {i} from playlist {playlist_id}')
            items.extend(response['items'])
            if 'nextPageToken' in response:
                npt = response['nextPageToken']
                i += 1
            else:
                break
        return items
    
    def get_videos_from_playlist_items(self, playlist_items):
        videos = []
        max_results = 50
        length = len(playlist_items)
        i = 0
        while i * max_results < length:
            top = max_results * (i + 1)
            if top > length: top = length
            ids = ",".join([x['snippet']['resourceId']['videoId'] for x in playlist_items[max_results*i:top]])
            request = self.youtube.videos().list(
                part="snippet",
                id=ids
            )
            try:
                response = request.execute()
            except HttpError as e:
                self.check_over_quota(e)
            self.logger.debug(f'Retrieved video info for videos: {ids}')
            videos.extend(response['items'])
            i += 1
        for video in videos:
            video['tvid'], video['part'] = self.get_tvid_from_yt_video(video)
            video['timestamp'] = self.get_timestamp_from_yt_video(video)
        return videos
    
    def get_playlist_videos(self, playlist_id):
        return self.get_videos_from_playlist_items(self.get_playlist_items(playlist_id))
    
    def get_channel_videos(self):
        request = self.youtube.channels().list(part="contentDetails", mine=True)
        try:
            r = request.execute()
            self.logger.debug('Retrieved channel upload playlist')
            uploads = r['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        except HttpError as e:
            self.check_over_quota(e)
        return self.get_playlist_videos(uploads)
    
    @staticmethod
    def get_tvid_from_yt_video(video):
        tvid = youtube_uploader.parse_tags(video, 'tvid')
        if tvid:
            tvid = tvid.split('p', 1)
            id = int(tvid[0])
            if len(tvid) > 1: part = int(tvid[1])
            else: part = None
            return id, part
        else: return None, None
    
    @staticmethod
    def get_timestamp_from_yt_video(video):
        timestamp = youtube_uploader.parse_tags(video, 'timestamp')
        if timestamp != None:
            timestamp = datetime.datetime.fromtimestamp(float(timestamp))
        return timestamp
    
    @staticmethod
    def parse_tags(video, tag_id:str):
        tag_id = tag_id + ':'
        result = None
        if 'tags' in video['snippet']:
            for tag in video['snippet']['tags']:
                if tag[:len(tag_id)] == tag_id:
                    result = tag[len(tag_id):]
        return result

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
            self.logger.debug(f'Added video {video_id} to playlist {playlist_id} at position {pos}')
            return r
        except HttpError as e:
            self.check_over_quota(e)
    
    def set_video_playlist_pos(self, video_id, playlist_item_id, playlist_id, pos):
        request = self.youtube.playlistItems().update(
            part="snippet",
            body={
                "id": playlist_item_id,
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
            self.logger.debug(f'Moved item {video_id} to position {pos} in playlist {playlist_id}')
            return r
        except HttpError as e:
            self.check_over_quota(e)

    def insert_into_playlist(self, video, playlist_id, reverse=False):
        self.logger.debug(f'Inserting video {video["id"]} into playlist {playlist_id} at position according to timestamp')
        playlist_items = self.get_playlist_items(playlist_id)
        videos = self.get_videos_from_playlist_items(playlist_items)
        videos = self.sort_playlist_by_timestamp(playlist_id, reverse=reverse, playlist_items=playlist_items, videos=videos)
        if videos:
            domain = range(len(videos))
            if reverse:
                for i in domain:
                    if video['timestamp'] == videos[i]['timestamp'] and video['part'] > videos[i]['part']:
                        self.add_video_to_playlist(video['id'], playlist_id, pos=i)
                        return i
                    elif video['timestamp'] > videos[i]['timestamp']:
                        self.add_video_to_playlist(video['id'], playlist_id, pos=i)
                        return i
                self.add_video_to_playlist(video['id'], playlist_id, pos=len(videos))
                return len(videos)
            else:
                for i in domain:
                    if video['timestamp'] == videos[i]['timestamp'] and video['part'] < videos[i]['part']:
                        self.add_video_to_playlist(video['id'], playlist_id, pos=i)
                        return i
                    elif video['timestamp'] < videos[i]['timestamp']:
                        self.add_video_to_playlist(video['id'], playlist_id, pos=i)
                        return i
                self.add_video_to_playlist(video['id'], playlist_id, pos=len(videos))
                return len(videos)
        else:
            if reverse:
                self.add_video_to_playlist(video['id'], playlist_id, pos=0)
            else:
                self.add_video_to_playlist(video['id'], playlist_id, pos=-1)
                    

    def check_sortable(self, videos):
        dupes = {}
        no_part = []
        no_id = []
        for video in videos:
            if video['tvid'] == None or video['timestamp'] == None:
                no_id.append(video['id'])
            if video['timestamp'] in dupes:
                dupes[video['timestamp']].append(video)
            else:
                dupes[video['timestamp']] = [video]
        for timestamp in dupes:
            if len(dupes[timestamp]) > 1:
                for video in dupes[timestamp]:
                    if video['part'] == None:
                        no_part.append(video['id'])
        if no_id != []:
            self.logger.error(f"There were videos found in the specified playlist to be sorted without a valid tvid or timestamp tag. As such this playlist cannot be reliably sorted. The videos specified are: {','.join(no_id)}")
            return False
        elif no_part != []:
            self.logger.error(f"There were videos found in the specified playlist to be sorted that has duplicate timestamp/tvid tags, but no part specified. As such this playlist cannot be reliably sorted. The videos specified are: {','.join(no_part)}")
            return False
        else:
            return True
    
    def sort_playlist_by_timestamp(self, playlist_id, reverse=False, playlist_items=None, videos=None):
        self.logger.debug(f'Sorting playlist {playlist_id} according to timestamp and part')
        if not playlist_items:
            playlist_items = self.get_playlist_items(playlist_id)
            videos = self.get_videos_from_playlist_items(playlist_items)
        elif not videos:
            videos = self.get_videos_from_playlist_items(playlist_items)
        if self.check_sortable(videos):
            videos.sort(reverse=reverse, key=lambda x: (x['timestamp'], x['part']))
        else:
            return False
        i = 0
        while i < len(videos):
            if videos[i]['id'] != playlist_items[i]['snippet']['resourceId']['videoId']:
                j = i + 1
                while videos[i]['id'] != playlist_items[j]['snippet']['resourceId']['videoId'] and j <= len(videos): j+=1
                if j < len(videos):
                    self.set_video_playlist_pos(playlist_items[j]['snippet']['resourceId']['videoId'], playlist_items[j]['id'], playlist_id, i)
                    playlist_items.insert(i, playlist_items.pop(j))
                else:
                    self.logger.error('An error has occurred while sorting the playlist')
                    return False
            else:
                i+=1
        return videos

    def check_over_quota(self, e: HttpError):
        if e.content:
            c = json.loads(e.content)
            if c['error']['errors'][0]['domain'] == 'youtube.quota' and c['error']['errors'][0]['reason'] == 'quotaExceeded':
                self.logger.error(f'YouTube client quota has been exceeded!')
                raise YouTubeOverQuota
            else:
                self.logger.error(e.resp)
                self.logger.error(e.content)
    
class YouTubeOverQuota(Exception):
    """ called when youtube upload quota is exceeded """
    pass