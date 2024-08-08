import logging
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent
from twitchAPI.helper import first
from .util import get_live
from .video import LiveStream
from .database import BaseDatabase
from pathlib import Path
import asyncio
from datetime import datetime, timezone

RETRY_COUNT = 5

class Channel():
    
    def __init__(
        self,
        database: BaseDatabase,
        name: str,
        id: str,
        live: bool,
        download_dir: Path,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        quality: str='best',
    ):
        self.logger = logging.getLogger(f'vodloader.{name}')
        self.database = database
        self.name = name
        self.id = id
        self.url = 'https://www.twitch.tv/' + self.name
        self.live = live
        self.twitch = twitch
        self.eventsub = eventsub
        self.quality = quality
        self.download_dir = download_dir
        self.subscriptions = []

    @classmethod
    async def create(
        cls,
        database: BaseDatabase,
        name: str,
        download_dir: Path,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        quality: str = 'best',
    ):
        user = await first(twitch.get_users(logins=[name]))
        live = await get_live(twitch, user.id)
        self = cls(
            database,
            name,
            user.id,
            live,
            download_dir,
            twitch,
            eventsub,
            quality,
        )
        await database.add_twitch_user(user.id, user.login, name, True, quality)
        await self.subscribe()
        return self

    async def on_online(self, event: StreamOnlineEvent):
        if event.event.type == 'live' and not self.live:

            self.live = True
            self.logger.info(f'{self.name} has gone live!')
            stream = None
            retry = 0
            while stream == None:
                stream = await first(self.twitch.get_streams(user_id=self.id))
                if stream == None:
                    retry += 1
                    if retry == RETRY_COUNT:
                        raise StreamUnretrievable()
                    else:
                        self.logger.warn(f'Could not retrieve current livestream from Twitch. Retrying #{retry}/{RETRY_COUNT}')
                        await asyncio.sleep(5)

            self.livestream = LiveStream(
                database=self.database,
                stream=stream,
                directory=self.download_dir,
                quality=self.quality)
            
            await self.database.add_twitch_stream(
                id=event.event.id,
                user=event.event.broadcaster_user_id,
                title=stream.title,
                category_id=stream.game_id,
                category_name=stream.game_name,
                started_at=event.event.started_at
            )
            await self.livestream.download_stream()
            ended_at = datetime.now(timezone.utc)
            self.live = False
            self.livestream = None
            await self.database.end_twitch_stream(event.event.id, ended_at)

    async def on_offline(self, event: StreamOfflineEvent):
        self.live = False
        self.logger.info(f'{self.name} has gone offline')
    
    async def on_update(self, event: ChannelUpdateEvent):
        self.logger.info(f'{self.name} has updated its information')
        update_id = await self.database.add_twitch_update(
            user=event.event.broadcaster_user_id,
            timestamp=datetime.now(timezone.utc),
            title=event.event.title,
            category_name=event.event.category_name,
            category_id=event.event.category_id
        )

    async def get_live(self):
        self.live = get_live(self.twitch, self.id)
        return self.live
    
    async def subscribe(self):
        self.logger.info('Subscribing to webhooks')
        self.subscriptions = []
        
        self.subscriptions.append(
            await self.eventsub.listen_stream_online(self.id, self.on_online)
        )
        self.subscriptions.append(
            await self.eventsub.listen_stream_offline(self.id, self.on_offline)
        )
        self.subscriptions.append(
            await self.eventsub.listen_channel_update_v2(self.id, self.on_update)
        )
        
    
    async def subscribe_async(self):
        self.logger.info('Subscribing to webhooks')
        self.subscriptions = []
        tasks = [
            asyncio.create_task(
                self.eventsub.listen_stream_online(self.id, self.on_online)
            ),
            asyncio.create_task(
                self.eventsub.listen_stream_offline(self.id, self.on_offline)
            ),
            asyncio.create_task(
                self.eventsub.listen_channel_update_v2(self.id, self.on_update)
            )
        ]
        for task in tasks:
            self.subscriptions.append(await task)

    async def unsubscribe(self):
        self.logger.info('Unsubscribing from webhooks')
        tasks = []
        for sub in self.subscriptions:
            tasks.append(
                asyncio.create_task(
                    self.eventsub.unsubscribe_topic(sub)
                )
            )
        for task in tasks:
            await task

    def __str__(self):
        return self.name

class StreamUnretrievable(Exception): pass
