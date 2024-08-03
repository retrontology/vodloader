import streamlink
import logging
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent
from twitchAPI.helper import first
from .util import get_live
from .video import LiveStream

class Channel():
    
    def __init__(
        self,
        name: str,
        id: str,
        live: bool,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        backlog: bool=False,
        chapters: str='titles',
        quality: str='best',
        timezone: str='America/New_York',
    ):
        self.logger = logging.getLogger(f'vodloader.channel.{name}')
        self.name = name
        self.id = id
        self.url = 'https://www.twitch.tv/' + self.name
        self.live = live
        self.twitch = twitch
        self.eventsub = eventsub
        self.backlog = backlog
        self.chapters = chapters
        self.quality = quality
        self.timezone = timezone
        self.subscriptions = []


    @classmethod
    async def create(
        cls,
        name: str,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        backlog: bool=False,
        chapters: str='titles',
        quality: str='best',
        timezone: str='America/New_York',
    ):
        user = await first(twitch.get_users(logins=[name]))
        live = await get_live(twitch, user.id)
        self = cls(
            name,
            user.id,
            live,
            twitch,
            eventsub,
            backlog,
            chapters,
            quality,
            timezone,
        )
        await self.subscribe()
        return self

    async def on_online(self, event: StreamOnlineEvent):
        if not self.live:
            self.live = True
            self.logger.info(f'{self.channel} has gone live!')
            streams = await self.twitch.get_streams(user_id=self.id)
            stream = streams['data'][0]
            self.livestream = LiveStream(stream, backlog=False, quality=self.quality)

    async def on_offline(self, event: StreamOfflineEvent):
        self.live = False
        self.logger.info(f'{self.channel} has gone offline')
    
    async def on_update(self, event: ChannelUpdateEvent):
        self.logger.info(f'{self.channel} has updated it\'s information')

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

    async def unsubscribe(self):
        self.logger.info('Unsubscribing from webhooks')
        for sub in self.subscriptions:
            await self.eventsub.unsubscribe_topic(sub)

    def __str__(self):
        return self.name
