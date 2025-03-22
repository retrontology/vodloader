import logging
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from vodloader.models import *
from vodloader.util import RETRY_COUNT, StreamUnretrievable
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.helper import first
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent


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
            await self.webhook.listen_stream_online(f'{self.id}', self.on_online)
        )
        subscriptions.append(
            await self.webhook.listen_stream_offline(f'{self.id}', self.on_offline)
        )
        subscriptions.append(
            await self.webhook.listen_channel_update_v2(f'{self.id}', self.on_update)
        )

        self.subscriptions[channel.id] = subscriptions


    # Callback for when the webhook receives an online event
    async def on_online(self, event: StreamOnlineEvent):
        
        channel = TwitchChannel.get(id=event.event.broadcaster_user_id)

        if not channel:
            self.logger.error(f"A Channel Online Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
            return
        
        self.logger.info(f'{channel.name} has gone live!')

        await download_stream()


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
    async def download_stream(self, channel: TwitchChannel, path:Path, quality:str='best'):
        self.logger.info(f'Downloading stream from {channel.name} to {path}')

        stream = None
        retry = 0
        while stream == None:
            stream = await first(twitch.get_streams(user_id=f'{self.id}'))
            if stream == None:
                retry += 1
                if retry >= RETRY_COUNT:
                    raise StreamUnretrievable()
                else:
                    self.logger.warning(f'Could not retrieve current livestream from Twitch. Retrying #{retry}/{RETRY_COUNT}')
                    await asyncio.sleep(5)

        twitch_stream = TwitchStream(
            id=event.event.id,
            channel=event.event.broadcaster_user_id,
            title=stream.title,
            category_id=stream.game_id,
            category_name=stream.game_name,
            started_at=event.event.started_at
        )
        await twitch_stream.save()
        video_file = VideoFile(
            id=uuid4().__str__(),
            stream=stream.id,
            channel=stream.channel,
            quality=quality,
            path=path,
            started_at=datetime.now(timezone.utc),
        )
        await video_file.save()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._download)
        await video_file.end()
        self.logger.info(f'Finished downloading stream from {self.url} to {self.path}')
        return VideoFile
    

    # Internal function for downloading stream in executor
    def _download(self, path:Path, quality:str="best"):
        stream = self.get_stream()
        buffer = stream.open()
        with open(self.path, 'wb') as f:
            while not self.ended:
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
        db_channels = await TwitchChannel.get_many(active=True)
        for channel in db_channels:
            await self.subscribe(channel)


    # Stop the service TBD
    async def stop(self):
        pass


