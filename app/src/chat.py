import irc.bot
from time import sleep
import string
import random
import logging

PASSWORD_LENGTH = 16
TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667

class bot(irc.bot.SingleServerIRCBot):

    def __init__(self):
        self.logger = logging.getLogger('vodloader.chatbot')
        self.username = self.gen_username()
        self.password = self.gen_password()
        spec = irc.bot.ServerSpec(TWITCH_IRC_SERVER, TWITCH_IRC_PORT, self.password)
        super().__init__([spec], self.username, self.username)
    
    @staticmethod
    def gen_password(length=PASSWORD_LENGTH):
        return ''.join(
            random.choice(
                string.ascii_uppercase + 
                string.digits + 
                string.ascii_lowercase
            ) for _ in range(length)
        )
    
    @staticmethod
    def gen_username():
        return 'justinfan' + str(random.randint(100,9999))
    
    # meant to be overwritten
    def welcome_callback(self, c, e):
        pass

    def on_welcome(self, c, e):
        self.logger.info('Joined Twitch IRC server!')
        c.cap('REQ', ':twitch.tv/membership')
        c.cap('REQ', ':twitch.tv/tags')
        c.cap('REQ', ':twitch.tv/commands')
        self.welcome_callback(c, e)
    
    def join_channel(self, channel):
        channel = f'#{channel.lower()}'
        if not channel in self.channels:
            self.connection.join(channel)

    def on_join(self, c, e):
        self.logger.debug(f'Joined {e.target}!')

    def on_pubmsg(self, c, e):
        pass
