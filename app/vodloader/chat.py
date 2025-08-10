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
            # Close any existing connections first
            await self._disconnect_async()
            
            # Generate new credentials for each connection
            self.username = self.gen_username()
            self.password = self.gen_password()
            
            self.logger.info(f'Connecting to {TWITCH_IRC_SERVER}:{TWITCH_IRC_PORT} as {self.username}')
            
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(TWITCH_IRC_SERVER, TWITCH_IRC_PORT),
                timeout=30.0
            )
            
            # Send authentication (anonymous users don't need oauth prefix)
            await self._send_raw(f'PASS {self.password}')
            await self._send_raw(f'NICK {self.username}')
            
            # Request capabilities
            await self._send_raw('CAP REQ :twitch.tv/membership')
            await self._send_raw('CAP REQ :twitch.tv/tags')
            await self._send_raw('CAP REQ :twitch.tv/commands')
            
            self.logger.info('Connected to Twitch IRC server')
            return True
            
        except asyncio.TimeoutError:
            self.logger.error('Connection timeout')
            return False
        except Exception as e:
            self.logger.error(f'Failed to connect: {e}')
            return False

    async def disconnect(self):
        """Disconnect from Twitch IRC server"""
        await self._disconnect_async()

    async def _disconnect_async(self):
        """Internal async disconnect implementation"""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                self.logger.error(f'Error closing writer: {e}')
        self.reader = None
        self.writer = None
        self.channels.clear()

    async def _send_raw(self, message: str):
        """Send raw IRC message"""
        if not self.writer:
            self.logger.warning('Attempted to send message without active connection')
            return
            
        try:
            self.writer.write(f'{message}\r\n'.encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            self.logger.error(f'Error sending message "{message}": {e}')
            raise

    async def join_channel(self, channel: TwitchChannel) -> None:
        """Join a Twitch channel"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name not in self.channels:
            await self._send_raw(f'JOIN {channel_name}')

    async def leave_channel(self, channel: TwitchChannel) -> None:
        """Leave a Twitch channel"""
        channel_name = f'#{channel.login.lower()}'
        if channel_name in self.channels:
            await self._send_raw(f'PART {channel_name}')

    def _parse_irc_message(self, raw_message: str) -> dict:
        """Parse IRC message into components"""
        message = {'tags': {}, 'source': '', 'command': '', 'parameters': []}
        
        try:
            # Parse tags
            if raw_message.startswith('@'):
                tags_end = raw_message.find(' ')
                if tags_end == -1:
                    return message  # Malformed message
                    
                tags_str = raw_message[1:tags_end]
                raw_message = raw_message[tags_end + 1:]
                
                for tag in tags_str.split(';'):
                    if '=' in tag:
                        key, value = tag.split('=', 1)
                        # Unescape tag values
                        value = value.replace('\\s', ' ').replace('\\n', '\n').replace('\\r', '\r').replace('\\\\', '\\')
                        message['tags'][key] = value
                    else:
                        message['tags'][tag] = True

            # Parse source
            if raw_message.startswith(':'):
                source_end = raw_message.find(' ')
                if source_end == -1:
                    return message  # Malformed message
                    
                message['source'] = raw_message[1:source_end]
                raw_message = raw_message[source_end + 1:]

            # Parse command and parameters
            parts = raw_message.split(' ')
            if not parts:
                return message  # Malformed message
                
            message['command'] = parts[0].upper()
            
            # Handle parameters
            for i, part in enumerate(parts[1:], 1):
                if part.startswith(':'):
                    # Trailing parameter - join the rest
                    message['parameters'].append(' '.join(parts[i:])[1:])
                    break
                else:
                    message['parameters'].append(part)

        except Exception as e:
            self.logger.error(f'Error parsing IRC message: {e}')
            
        return message

    async def _handle_message(self, parsed_message: dict):
        """Handle parsed IRC message"""
        command = parsed_message['command']
        
        try:
            if command == 'PING':
                if parsed_message['parameters']:
                    await self._send_raw(f'PONG :{parsed_message["parameters"][0]}')
                    
            elif command == '001':  # Welcome message
                self.logger.info('Successfully authenticated with Twitch IRC')
                
            elif command == 'JOIN':
                if parsed_message['parameters'] and parsed_message['source']:
                    channel = parsed_message['parameters'][0]
                    username = parsed_message['source'].split('!')[0] if '!' in parsed_message['source'] else parsed_message['source']
                    if username == self.username:
                        self.channels.add(channel)
                        self.logger.info(f'Joined {channel}')
                        
            elif command == 'PART':
                if parsed_message['parameters'] and parsed_message['source']:
                    channel = parsed_message['parameters'][0]
                    username = parsed_message['source'].split('!')[0] if '!' in parsed_message['source'] else parsed_message['source']
                    if username == self.username:
                        self.channels.discard(channel)
                        self.logger.info(f'Left {channel}')
                        
            elif command == 'PRIVMSG':
                await self._handle_privmsg(parsed_message)
                
            elif command == 'CLEARCHAT':
                await self._handle_clearchat(parsed_message)
                
            elif command == 'CLEARMSG':
                await self._handle_clearmsg(parsed_message)
                
        except Exception as e:
            self.logger.error(f'Error handling {command}: {e}')

    async def _handle_privmsg(self, parsed_message: dict):
        """Handle PRIVMSG command"""
        if not parsed_message['parameters']:
            return
            
        mock_event = MockEvent(
            tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
            source=parsed_message['source'],
            target=parsed_message['parameters'][0],
            arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
        )
        
        message = Message.from_event(mock_event)
        await message.save()

    async def _handle_clearchat(self, parsed_message: dict):
        """Handle CLEARCHAT command"""
        if not parsed_message['parameters']:
            return
            
        mock_event = MockEvent(
            tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
            source=parsed_message['source'],
            target=parsed_message['parameters'][0],
            arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
        )
        
        clearchat_event = ClearChatEvent.from_event(mock_event)
        await clearchat_event.save()

    async def _handle_clearmsg(self, parsed_message: dict):
        """Handle CLEARMSG command"""
        if not parsed_message['parameters']:
            return
            
        mock_event = MockEvent(
            tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
            source=parsed_message['source'],
            target=parsed_message['parameters'][0],
            arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
        )
        
        clearmsg_event = ClearMsgEvent.from_event(mock_event)
        await clearmsg_event.save()

    async def _listen(self):
        """Listen for IRC messages"""
        while self.running and self.reader:
            try:
                # Use asyncio.wait_for to add timeout to readline
                line = await asyncio.wait_for(self.reader.readline(), timeout=300.0)  # 5 minute timeout
                
                if not line:
                    self.logger.warning('Connection lost - no data received')
                    break
                    
                try:
                    raw_message = line.decode('utf-8').strip()
                except UnicodeDecodeError as e:
                    self.logger.warning(f'Failed to decode message: {e}')
                    continue
                    
                if raw_message:
                    parsed_message = self._parse_irc_message(raw_message)
                    if parsed_message.get('command'):  # Only handle valid messages
                        await self._handle_message(parsed_message)
                        
            except asyncio.TimeoutError:
                self.logger.warning('No data received for 5 minutes, connection may be stale')
                break
            except asyncio.CancelledError:
                self.logger.info('Listen task cancelled')
                break
            except Exception as e:
                self.logger.error(f'Error reading message: {e}')
                break

    async def start(self):
        """Start the bot with automatic reconnection"""
        self.running = True
        reconnect_delay = self._reconnect_delay
        
        try:
            while self.running:
                try:
                    self.logger.info('Attempting to connect to Twitch IRC...')
                    if await self.connect():
                        reconnect_delay = self._reconnect_delay  # Reset delay on successful connection
                        await self._listen()
                    else:
                        self.logger.error('Failed to connect to Twitch IRC')
                        
                    if self.running:  # Only reconnect if we're supposed to be running
                        self.logger.info(f'Reconnecting in {reconnect_delay} seconds...')
                        await asyncio.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, self._max_reconnect_delay)
                        
                except Exception as e:
                    self.logger.error(f'Unexpected error in bot start: {e}')
                    if self.running:
                        await asyncio.sleep(reconnect_delay)
                        
                finally:
                    await self._disconnect_async()
                    
        except asyncio.CancelledError:
            self.logger.info('Bot start task cancelled - stopping gracefully')
            self.running = False
        finally:
            await self._disconnect_async()

    async def stop(self):
        """Stop the bot gracefully"""
        self.logger.info('Stopping Twitch IRC bot...')
        self.running = False
        await self._disconnect_async()
        self.logger.info('Twitch IRC bot stopped')




# Create bot instance
bot = AsyncTwitchBot()
