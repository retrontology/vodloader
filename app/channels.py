import streamlink
import logging
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent
from twitchAPI.helper import first

class Channel():
    
    def __init__(
        self,
        name: str,
        user_id: str,
        twitch: Twitch,
        eventsub: EventSubWebhook,
        backlog: bool=False,
        chapters: str='titles',
        quality: str='best',
        timezone: str='America/New_York',
    ):
        self.logger = logging.getLogger(f'Channel.{name}')
        self.name = name
        self.user_id = user_id
        self.twitch = twitch
        self.eventsub = eventsub
        self.backlog = backlog
        self.chapters = chapters
        self.quality = quality
        self.timezone = timezone


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
        self = cls(
            name,
            user.id,
            twitch,
            eventsub,
            backlog,
            chapters,
            quality,
            timezone,
        )
        await eventsub.listen_stream_online(self.user_id, self.on_online)
        await eventsub.listen_stream_offline(self.user_id, self.on_offline)
        return self

    async def on_online(self, event: StreamOnlineEvent):
        self.logger.info('CHANNEL HAS GONE ONLINE')

    async def on_offline(self, event: StreamOfflineEvent):
        self.logger.info('CHANNEL HAS GONE OFFLINE OH NO!!!')
