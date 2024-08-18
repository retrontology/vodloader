import logging
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent
from twitchAPI.helper import first
from .util import get_live
from .video import LiveStream
from pathlib import Path
import asyncio
from datetime import datetime, timezone
from .models import *
from uuid import uuid4

RETRY_COUNT = 5

class Channel():
    
    def __init__(
        self,
        name: str,
        login: str,
        id: str,
        live: bool,
        download_dir: Path,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        quality: str='best',
    ):
        self.logger = logging.getLogger(f'vodloader.{name}')
        self.name = name
        self.login = login
        self.id = id
        self.live = live
        self.twitch = twitch
        self.eventsub = eventsub
        self.quality = quality
        self.download_dir = download_dir.joinpath(self.name)
        self.download_dir.mkdir(exist_ok=True)
        self.subscriptions = []

    @classmethod
    async def from_channel(
        self,
        channel: TwitchChannel,
        download_dir: Path,
        twitch: Twitch,
        eventsub: EventSubWebhook
    ):
        live = await get_live(twitch, channel.id)
        self = Channel(
            name=channel.name,
            login=channel.login,
            id=channel.id,
            live=live,
            download_dir=download_dir,
            twitch=twitch,
            eventsub=eventsub,
            quality=channel.quality
        )
        await self.subscribe()
        return self
    
    @classmethod
    async def create(
        cls,
        name: str,
        download_dir: Path,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        quality: str = 'best',
    ):
        user = await first(twitch.get_users(logins=[name]))

        if not user:
            raise ChannelDoesNotExist
        
        channel = TwitchChannel(
            id=user.id,
            login=user.login,
            name=user.display_name,
            active=True,
            quality=quality
        )
        await channel.save()
        
        self = await cls.from_channel(
            channel=channel,
            download_dir=download_dir,
            twitch=twitch,
            eventsub=eventsub
        )
        return self

    async def on_online(self, event: StreamOnlineEvent):
        if event.event.type == 'live' and not self.live:

            self.live = True
            self.logger.info(f'{self.name} has gone live!')
            stream = None
            retry = 0
            while stream == None:
                stream = await first(self.twitch.get_streams(user_id=f'{self.id}'))
                if stream == None:
                    retry += 1
                    if retry == RETRY_COUNT:
                        raise StreamUnretrievable()
                    else:
                        self.logger.warn(f'Could not retrieve current livestream from Twitch. Retrying #{retry}/{RETRY_COUNT}')
                        await asyncio.sleep(5)

            self.livestream = LiveStream(
                stream=stream,
                directory=self.download_dir,
                quality=self.quality)
            
            twitch_stream = TwitchStream(
                id=event.event.id,
                channel=event.event.broadcaster_user_id,
                title=stream.title,
                category_id=stream.game_id,
                category_name=stream.game_name,
                started_at=event.event.started_at
            )
            await twitch_stream.save()
            await self.livestream.download_stream()
            self.live = False
            self.livestream = None
            await twitch_stream.end()

    async def on_offline(self, event: StreamOfflineEvent):
        self.live = False
        self.logger.info(f'{self.name} has gone offline')
    
    async def on_update(self, event: ChannelUpdateEvent):
        self.logger.info(f'{self.name} has updated its information')
        update = TwitchChannelUpdate(
            id=uuid4().__str__(),
            channel=event.event.broadcaster_user_id,
            timestamp=datetime.now(timezone.utc),
            title=event.event.title,
            category_name=event.event.category_name,
            category_id=event.event.category_id
        )
        await update.save()

    async def get_live(self):
        self.live = get_live(self.twitch, f'{self.id}')
        return self.live
    
    async def subscribe(self):
        self.logger.info('Subscribing to webhooks')
        self.subscriptions = []
        
        self.subscriptions.append(
            await self.eventsub.listen_stream_online(f'{self.id}', self.on_online)
        )
        self.subscriptions.append(
            await self.eventsub.listen_stream_offline(f'{self.id}', self.on_offline)
        )
        self.subscriptions.append(
            await self.eventsub.listen_channel_update_v2(f'{self.id}', self.on_update)
        )
        
    
    async def subscribe_async(self):
        self.logger.info('Subscribing to webhooks')
        self.subscriptions = []
        tasks = [
            asyncio.create_task(
                self.eventsub.listen_stream_online(f'{self.id}', self.on_online)
            ),
            asyncio.create_task(
                self.eventsub.listen_stream_offline(f'{self.id}', self.on_offline)
            ),
            asyncio.create_task(
                self.eventsub.listen_channel_update_v2(f'{self.id}', self.on_update)
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
class ChannelDoesNotExist(Exception): pass
