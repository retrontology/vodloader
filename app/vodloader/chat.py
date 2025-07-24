import string
import random
import logging
import asyncio
import re
from typing import Set, Optional
from vodloader.models import Message, ClearChatEvent, ClearMsgEvent, TwitchChannel
from vodloader.util import MockEvent


PASSWORD_LENGTH = 16
TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667


class AsyncTwitchBot:
    _instance = None

    def __init__(self) -> None:
        self.logger = logging.getLogger('vodloader.chatbot')
        self.username = self.gen_username()
        self.password = self.gen_password()
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.channels: Set[str] = set()
        self.running = False
        self._reconnect_delay = 5
        self._max_reconnect_delay = 300

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
        return 'justinfan' + str(random.randint(100, 9999))

    async def connect(self) -> bool:
        """Connect to Twitch IRC server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                TWITCH_IRC_SERVER, TWITCH_IRC_PORT
            )
            
            # Send authentication
            await self._send_raw(f'PASS {self.password}')
            await self._send_raw(f'NICK {self.username}')
            
            # Request capabilities
            await self._send_raw('CAP REQ :twitch.tv/membership')
            await self._send_raw('CAP REQ :twitch.tv/tags')
            await self._send_raw('CAP REQ :twitch.tv/commands')
            
            self.logger.info('Connected to Twitch IRC server')
            return True
            
        except Exception as e:
            self.logger.error(f'Failed to connect: {e}')
            return False

    async def disconnect(self):
        """Disconnect from Twitch IRC server"""
        self.running = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        self.channels.clear()

    async def _send_raw(self, message: str):
        """Send raw IRC message"""
        if self.writer:
            self.writer.write(f'{message}\r\n'.encode('utf-8'))
            await self.writer.drain()

    def join_channel(self, channel: TwitchChannel) -> None:
        """Join a Twitch channel (sync interface for compatibility)"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name not in self.channels and self.writer:
            asyncio.create_task(self._send_raw(f'JOIN {channel_name}'))

    def leave_channel(self, channel: TwitchChannel) -> None:
        """Leave a Twitch channel (sync interface for compatibility)"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name in self.channels and self.writer:
            asyncio.create_task(self._send_raw(f'PART {channel_name}'))

    async def join_channel_async(self, channel: TwitchChannel) -> None:
        """Join a Twitch channel (async interface)"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name not in self.channels:
            await self._send_raw(f'JOIN {channel_name}')

    async def leave_channel_async(self, channel: TwitchChannel) -> None:
        """Leave a Twitch channel (async interface)"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name in self.channels:
            await self._send_raw(f'PART {channel_name}')

    def _parse_irc_message(self, raw_message: str) -> dict:
        """Parse IRC message into components"""
        message = {'tags': {}, 'source': '', 'command': '', 'parameters': []}
        
        # Parse tags
        if raw_message.startswith('@'):
            tags_end = raw_message.find(' ')
            tags_str = raw_message[1:tags_end]
            raw_message = raw_message[tags_end + 1:]
            
            for tag in tags_str.split(';'):
                if '=' in tag:
                    key, value = tag.split('=', 1)
                    message['tags'][key] = value
                else:
                    message['tags'][tag] = True

        # Parse source
        if raw_message.startswith(':'):
            source_end = raw_message.find(' ')
            message['source'] = raw_message[1:source_end]
            raw_message = raw_message[source_end + 1:]

        # Parse command and parameters
        parts = raw_message.split(' ')
        message['command'] = parts[0].upper()
        
        # Handle parameters
        for i, part in enumerate(parts[1:], 1):
            if part.startswith(':'):
                # Trailing parameter - join the rest
                message['parameters'].append(' '.join(parts[i:])[1:])
                break
            else:
                message['parameters'].append(part)

        return message

    async def _handle_message(self, parsed_message: dict):
        """Handle parsed IRC message"""
        command = parsed_message['command']
        
        try:
            if command == 'PING':
                await self._send_raw(f'PONG :{parsed_message["parameters"][0]}')
                
            elif command == '001':  # Welcome message
                self.logger.info('Successfully authenticated with Twitch IRC')
                
            elif command == 'JOIN':
                channel = parsed_message['parameters'][0]
                username = parsed_message['source'].split('!')[0]
                if username == self.username:
                    self.channels.add(channel)
                    self.logger.info(f'Joined {channel}')
                    
            elif command == 'PART':
                channel = parsed_message['parameters'][0]
                username = parsed_message['source'].split('!')[0]
                if username == self.username:
                    self.channels.discard(channel)
                    self.logger.info(f'Left {channel}')
                    
            elif command == 'PRIVMSG':
                # Create a mock event object for compatibility with existing Message.from_event
                mock_event = MockEvent(
                    tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
                    source=parsed_message['source'],
                    target=parsed_message['parameters'][0],
                    arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
                )
                
                message = Message.from_event(mock_event)
                await message.save()
                
            elif command == 'CLEARCHAT':
                mock_event = MockEvent(
                    tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
                    source=parsed_message['source'],
                    target=parsed_message['parameters'][0],
                    arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
                )
                
                clearchat_event = ClearChatEvent.from_event(mock_event)
                await clearchat_event.save()
                
            elif command == 'CLEARMSG':
                mock_event = MockEvent(
                    tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
                    source=parsed_message['source'],
                    target=parsed_message['parameters'][0],
                    arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
                )
                
                clearmsg_event = ClearMsgEvent.from_event(mock_event)
                await clearmsg_event.save()
                
        except Exception as e:
            self.logger.error(f'Error handling {command}: {e}')

    async def _listen(self):
        """Listen for IRC messages"""
        while self.running and self.reader:
            try:
                line = await self.reader.readline()
                if not line:
                    self.logger.warning('Connection lost')
                    break
                    
                raw_message = line.decode('utf-8').strip()
                if raw_message:
                    parsed_message = self._parse_irc_message(raw_message)
                    await self._handle_message(parsed_message)
                    
            except Exception as e:
                self.logger.error(f'Error reading message: {e}')
                break

    async def start(self):
        """Start the bot with automatic reconnection"""
        self.running = True
        reconnect_delay = self._reconnect_delay
        
        while self.running:
            try:
                if await self.connect():
                    reconnect_delay = self._reconnect_delay  # Reset delay on successful connection
                    await self._listen()
                    
                if self.running:  # Only reconnect if we're supposed to be running
                    self.logger.info(f'Reconnecting in {reconnect_delay} seconds...')
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)
                    
            except Exception as e:
                self.logger.error(f'Unexpected error: {e}')
                if self.running:
                    await asyncio.sleep(reconnect_delay)
                    
            finally:
                await self.disconnect()

    async def stop(self):
        """Stop the bot"""
        self.running = False
        await self.disconnect()

    def die(self):
        """Legacy sync method for stopping the bot"""
        self.running = False

    def disconnect_sync(self):
        """Legacy sync method for disconnecting"""
        if self.writer:
            asyncio.create_task(self.disconnect())

    # Alias for compatibility
    disconnect = disconnect_sync

    async def start_async(self):
        """Async start method for compatibility with run.py"""
        await self.start()


# Create singleton instance
bot = AsyncTwitchBot()
