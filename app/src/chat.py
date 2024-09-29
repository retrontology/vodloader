import irc.bot, irc.client
from .models import Message
import string
import random
import logging

PASSWORD_LENGTH = 16
TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667


class Bot(irc.bot.SingleServerIRCBot):

    def __init__(self) -> None:
        self.logger = logging.getLogger('vodloader.chatbot')
        self.username = self.gen_username()
        self.password = self.gen_password()
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
    
    # meant to be overwritten
    def welcome_callback(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        pass

    # meant to be overwritten
    def message_callback(self, message: Message) -> None:
        pass

    def on_welcome(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        self.logger.info('Connected to Twitch IRC server')
        conn.cap('REQ', ':twitch.tv/membership')
        conn.cap('REQ', ':twitch.tv/tags')
        conn.cap('REQ', ':twitch.tv/commands')
        self.welcome_callback(conn, event)
    
    def join_channel(self, channel: str) -> None:
        channel = f'#{channel.lower()}'
        if not channel in self.channels:
            self.connection.join(channel)

    def on_join(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        self.logger.info(f'Joined {event.target}')

    def on_pubmsg(self, conn: irc.client.ServerConnection, event: irc.client.Event) -> None:
        message = Message.from_event(event)
        self.message_callback(message)
