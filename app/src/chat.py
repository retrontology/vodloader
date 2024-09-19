import irc.bot, irc.client
from typing import Self, List, Dict, Tuple
import string
import random
import logging
import datetime

PASSWORD_LENGTH = 16
TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667

class Message():
    
    def __init__(
            self,
            id: str,
            content: str,
            channel: str,
            display_name: str,
            badge_info: str,
            badges: str,
            color: str,
            emotes: str,
            first_message: bool,
            flags: str,
            mod: bool,
            returning_chatter: bool,
            room_id: int,
            subscriber: bool,
            timestamp: datetime.datetime,
            turbo: bool,
            user_id: int,
            user_type: str,
        ) -> None:
        self.id = id
        self.content = content
        self.channel = channel
        self.display_name = display_name
        self.badge_info = badge_info
        self.badges = badges
        self.color = color
        self.emotes = emotes
        self.first_message = first_message
        self.flags = flags
        self.mod = mod
        self.returning_chatter = returning_chatter
        self.room_id = room_id
        self.subscriber = subscriber
        self.timestamp = timestamp
        self.turbo = turbo
        self.user_id = user_id
        self.user_type = user_type


    @classmethod
    def from_event(cls, event: irc.client.Event) -> Self:
        
        tags = {}
        for tag in event.tags:
            tags[tag['key']] = tag['value']

        return cls(
            id = tags['id'],
            content = event.arguments[0],
            channel = event.target[1:],
            display_name = tags['display-name'],
            badge_info = tags['badge-info'],
            badges = tags['badges'],
            color = tags['color'],
            emotes = tags['emotes'],
            first_message = tags['first-msg'] == '1',
            flags = tags['flags'],
            mod = tags['mod'] == '1',
            returning_chatter = tags['returning-chatter'] == '1',
            room_id = int(tags['room-id']),
            subscriber = tags['subscriber'] == '1',
            timestamp = datetime.datetime.fromtimestamp(float(tags['tmi-sent-ts'])/1000),
            turbo = tags['turbo'] == '1',
            user_id = int(tags['user-id']),
            user_type = tags['user-type'],
        )
    
    def parse_badges(self) -> List[str] | None:
        if self.badges == None:
            return None
        return self.badges.split(',')

    def parse_badge_info(self) -> Dict[str, str]:
        if self.badge_info == None:
            return None
        
        badge_info = {}
        for info in value.split(','):
            key, value = info.split('/', 1)
            badge_info[key] = value
        return badge_info
    
    def parse_emotes(self) -> Dict[int, List[Tuple[int, int]]]:
        if self.emotes == None:
            return None
        
        emotes = {}
        for emote in self.emotes.split('/'):
            number, places= emote.split(':', 1)
            index = []
            for place in places.split(','):
                start, end = place.split('-', 1)
                index.append((int(start), int(end)))
            emotes[int(number)] = index.copy()
        return emotes


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
