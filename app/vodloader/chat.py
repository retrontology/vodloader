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
        self.channels: Set[str] = set()  # Currently joined channels
        self.target_channels: Set[str] = set()  # Channels we should be in
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
            
            # Wait a moment for capabilities to be acknowledged
            await asyncio.sleep(1)
            
            # Rejoin all target channels
            await self._rejoin_target_channels()
            
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
        # Clear currently joined channels but keep target channels for reconnection
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
        
        # Add to target channels (persistent)
        self.target_channels.add(channel_name)
        
        # Join if we have an active connection and not already joined
        if self.writer and channel_name not in self.channels:
            await self._send_raw(f'JOIN {channel_name}')

    async def leave_channel(self, channel: TwitchChannel) -> None:
        """Leave a Twitch channel"""
        channel_name = f'#{channel.login.lower()}'
        
        # Remove from target channels (persistent)
        self.target_channels.discard(channel_name)
        
        # Leave if we have an active connection and currently joined
        if self.writer and channel_name in self.channels:
            await self._send_raw(f'PART {channel_name}')

    async def _rejoin_target_channels(self) -> None:
        """Rejoin all channels we should be connected to"""
        for channel_name in self.target_channels:
            try:
                await self._send_raw(f'JOIN {channel_name}')
                self.logger.info(f'Rejoining {channel_name}')
                # Small delay between joins to avoid rate limiting
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f'Failed to rejoin {channel_name}: {e}')

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
            
        try:
            mock_event = MockEvent(
                tags=[{'key': k, 'value': v} for k, v in parsed_message['tags'].items()],
                source=parsed_message['source'],
                target=parsed_message['parameters'][0],
                arguments=parsed_message['parameters'][1:] if len(parsed_message['parameters']) > 1 else ['']
            )
            
            message = Message.from_event(mock_event)
            await message.save()
            self.logger.debug(f'Saved message from {message.display_name}: {message.content[:50]}...')
        except Exception as e:
            self.logger.error(f'Failed to save message: {e}')

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
        last_ping = asyncio.get_event_loop().time()
        last_channel_check = asyncio.get_event_loop().time()
        ping_interval = 240  # Send ping every 4 minutes
        channel_check_interval = 300  # Check channels every 5 minutes
        
        while self.running and self.reader:
            try:
                # Use asyncio.wait_for to add timeout to readline
                line = await asyncio.wait_for(self.reader.readline(), timeout=30.0)  # 30 second timeout
                
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
                # Send periodic ping to keep connection alive and check channel status
                current_time = asyncio.get_event_loop().time()
                
                if current_time - last_ping > ping_interval:
                    try:
                        await self._send_raw('PING :tmi.twitch.tv')
                        last_ping = current_time
                        self.logger.debug('Sent keepalive ping')
                    except Exception as e:
                        self.logger.error(f'Failed to send keepalive ping: {e}')
                        break
                
                # Periodically check if we're in all target channels
                if current_time - last_channel_check > channel_check_interval:
                    missing_channels = self.target_channels - self.channels
                    if missing_channels:
                        self.logger.warning(f'Not joined to expected channels: {missing_channels}. Attempting to rejoin...')
                        await self._rejoin_target_channels()
                    last_channel_check = current_time
                
                continue  # Continue listening instead of breaking
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

    def get_channel_status(self) -> dict:
        """Get current channel connection status"""
        return {
            'target_channels': list(self.target_channels),
            'joined_channels': list(self.channels),
            'missing_channels': list(self.target_channels - self.channels),
            'connected': self.writer is not None,
            'running': self.running
        }




# Create bot instance
bot = AsyncTwitchBot()
