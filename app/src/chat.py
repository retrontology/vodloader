import irc.bot, irc.client
import string
import random
import logging
import asyncio
from .models import Message, ClearChatEvent, ClearMsgEvent

PASSWORD_LENGTH = 16
TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667


class Bot(irc.bot.SingleServerIRCBot):

    def __init__(self) -> None:
        self.logger = logging.getLogger('vodloader.chatbot')
        self.username = self.gen_username()
        self.password = self.gen_password()
        self.loop = None
        spec = irc.bot.ServerSpec(TWITCH_IRC_SERVER, TWITCH_IRC_PORT, self.password)
        super().__init__([spec], self.username, self.username)
    
    @staticmethod
    def gen_password(length=PASSWORD_LENGTH) -> str:
        return ''.join(
            random.choice(
                string.ascii_uppercase + 
                string.digits + 
                string.ascii_lowercase
            ) for _ in range(length)
        )
    
    @staticmethod
    def gen_username() -> str:
        return 'justinfan' + str(random.randint(100,9999))
    
    def join_channel(self, channel: str) -> None:
        channel = f'#{channel.lower()}'
        if not channel in self.channels:
            self.connection.join(channel)

    def leave_channel(self, channel: str) -> None:
        channel = f'#{channel.lower()}'
        if channel in self.channels:
            self.connection.quit(channel)

    def on_join(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        username = event.source.split('!', 1)[0]
        if username == self.username:
            self.logger.info(f'Joined {event.target}')
    
    def on_welcome(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        self.logger.info('Connected to Twitch IRC server')
        conn.cap('REQ', ':twitch.tv/membership')
        conn.cap('REQ', ':twitch.tv/tags')
        conn.cap('REQ', ':twitch.tv/commands')

    def on_pubmsg(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        message = Message.from_event(event)
        self.loop.run_until_complete(message.save())

    def on_clearchat(self, conn: irc.client.ServerConnection = None, event: irc.client.Event = None) -> None:
        clearchat_event = ClearChatEvent.from_event(event)
        self.loop.run_until_complete(clearchat_event.save())

    def on_clearmsg(self, conn: irc.client.ServerConnection = None, event: irc.client.Event = None) -> None:
        clearmsg_event = ClearMsgEvent.from_event(event)
        self.loop.run_until_complete(clearmsg_event.save())
    
    def start(self):
        self.loop = asyncio.new_event_loop()
        super().start()
