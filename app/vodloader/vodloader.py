import logging
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from functools import partial
from vodloader.models import *
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.helper import first
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent


CHUNK_SIZE = 8192
MAX_VIDEO_LENGTH = 60*(60*12-15)
RETRY_LIMIT = 10
VIDEO_EXTENSION = 'ts'
MAX_LENGTH=60*(60*12-15)


class VODLoader():


    logger: logging.Logger = logging.getLogger('vodloader')


    def __init__(
            self,
            download_dir:Path,
            host:str,
            port:int=8000,
    ):
        self.download_dir: Path = Path(download_dir)
        self.host = host
        self.port = port
        self.webhook = None
        self.twitch = None
        self.subscriptions = {}

    # Initialize Twitch client
    async def init_twitch(self):
        self.twitch = await TwitchClient.get_twitch()

    # Initialize Webhook
    async def init_webhook(self):

        if not self.twitch:
            await self.init_twitch()
            
        self.logger.info(f'Initializing EventSub Webhook')
        self.webhook = EventSubWebhook(f"https://{self.host}", self.port, self.twitch)
        await self.webhook.unsubscribe_all()
        self.webhook.start()


    # Subscribe to a Twitch Channel's Webhooks
    async def subscribe(self, channel: TwitchChannel):

        self.logger.info(f'Subscribing to webhooks for {channel.name}')

        subscriptions = []
        if channel.id in self.subscriptions:
            subscriptions = self.subscriptions[channel.id]

        subscriptions.append(
            await self.webhook.listen_stream_online(f'{channel.id}', self.on_online)
        )
        subscriptions.append(
            await self.webhook.listen_stream_offline(f'{channel.id}', self.on_offline)
        )
        subscriptions.append(
            await self.webhook.listen_channel_update_v2(f'{channel.id}', self.on_update)
        )

        self.subscriptions[channel.id] = subscriptions


    # Callback for when the webhook receives an online event
    async def on_online(self, event: StreamOnlineEvent):
        
        channel = await TwitchChannel.get(id=event.event.broadcaster_user_id)

        if not channel:
            self.logger.error(f"A Channel Online Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
            return
        
        self.logger.info(f'{channel.name} has gone live!')

        await self.download_stream(channel, )


    # Callback for when the webhook receives an offline event
    async def on_offline(self, event: StreamOfflineEvent):

        channel = TwitchChannel.get(id=event.event.broadcaster_user_id)

        if not channel:
            self.logger.error(f"A Channel Offline Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
            return

        self.logger.info(f'{channel.name} has gone offline')


    # Callback for when the webhook receives an update event
    async def on_update(self, event: ChannelUpdateEvent):

        channel = TwitchChannel.get(id=event.event.broadcaster_user_id)

        if not channel:
            self.logger.error(f"A Channel Update Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
            return

        self.logger.info(f'{event.event.broadcaster_user_name} has updated its information')

        update = TwitchChannelUpdate(
            id=uuid4().__str__(),
            channel=channel.id,
            timestamp=datetime.now(timezone.utc),
            title=event.event.title,
            category_name=event.event.category_name,
            category_id=event.event.category_id
        )
        await update.save()


    # Function to download stream from a Twitch Channel
    async def download_stream(self, channel: TwitchChannel):

        self.logger.info(f'Grabbing stream info from {channel.name}')

        stream_info = None
        count = 0
        while stream_info == None:
            stream_info = await first(self.twitch.get_streams(user_id=f'{channel.id}'))
            if stream_info == None:
                count += 1
                if count >= RETRY_LIMIT:
                    raise StreamUnretrievable()
                else:
                    self.logger.warning(f'Could not retrieve current livestream from Twitch. Retrying #{count}/{RETRY_LIMIT}')
                    await asyncio.sleep(5)

        twitch_stream = TwitchStream(
            id=stream_info.id,
            channel=channel.id,
            title=stream_info.title,
            category_id=stream_info.game_id,
            category_name=stream_info.game_name,
            started_at=stream_info.started_at
        )
        await twitch_stream.save()

        name = f'{stream_info.user_login}-{stream_info.title}-{stream_info.id}.{VIDEO_EXTENSION}'
        path = self.download_dir.joinpath(name)

        self.logger.info(f'Downloading stream from {channel.name} to {path}')

        video_file = VideoFile(
            id=uuid4().__str__(),
            stream=stream_info.id,
            channel=channel.id,
            quality=channel.quality,
            path=path,
            started_at=datetime.now(timezone.utc),
        )
        await video_file.save()

        loop = asyncio.get_event_loop()
        download_function = partial(self._download, channel=channel, path=path)
        await loop.run_in_executor(None, download_function)

        end_time = datetime.now(timezone.utc)
        await twitch_stream.end(end_time)
        await video_file.end(end_time)

        self.logger.info(f'Finished downloading stream from {channel.name} to {path}')
    

    # Internal function for downloading stream in executor
    def _download(self, channel: TwitchChannel, path:Path):
        stream = channel.get_stream()
        buffer = stream.open()
        with open(path, 'wb') as f:
            try:
                data = buffer.read(CHUNK_SIZE)
                while data:
                    f.write(data)
                    data = buffer.read(CHUNK_SIZE)
            except Exception as e:
                self.logger.error(e)
        buffer.close()


    # Start the service 
    async def start(self):
        await self.init_webhook()
        channels = await TwitchChannel.get_many(active=True)
        for channel in channels:
            await self.subscribe(channel)


    # Stop the service TBD
    async def stop(self):
        pass


class StreamUnretrievable(Exception): pass
