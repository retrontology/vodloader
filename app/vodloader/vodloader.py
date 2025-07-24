import logging
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pathlib import Path
import asyncio
from functools import partial
from vodloader.models import *
from vodloader import config
from vodloader.twitch import webhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent
from vodloader.post import transcode_queue


CHUNK_SIZE = 8192
VIDEO_EXTENSION = 'ts'
NAMING_SCHEME = '{channel}-{title}-{stream}-part-{part}.{ext}'
CUTOFF = timedelta(hours=8)


logger: logging.Logger = logging.getLogger('vodloader')


# Subscribe to a Twitch Channel's Webhooks
async def subscribe(channel: TwitchChannel):

    logger.info(f'Subscribing to webhooks for {channel.name}')

    online_id = await webhook.listen_stream_online(f'{channel.id}', _on_online)
    channel.webhook_online = online_id

    offline_id = await webhook.listen_stream_offline(f'{channel.id}', _on_offline)
    channel.webhook_offline = offline_id

    update_id = await webhook.listen_channel_update_v2(f'{channel.id}', _on_update)
    channel.webhook_update = update_id
    
    await channel.save()


# Subscribe to a Twitch Channel's Webhooks
async def unsubscribe(channel: TwitchChannel):

    logger.info(f'Unsubscribing to webhooks for {channel.name}')

    if channel.webhook_online != None:
        await webhook.unsubscribe_topic(channel.webhook_online)
        channel.webhook_online = None
    
    if channel.webhook_offline != None:
        await webhook.unsubscribe_topic(channel.webhook_offline)
        channel.webhook_offline = None

    if channel.webhook_update != None:
        await webhook.unsubscribe_topic(channel.webhook_update)
        channel.webhook_update = None

    await channel.save()


# Callback for when the webhook receives an online event
async def _on_online(event: StreamOnlineEvent):
    
    channel = await TwitchChannel.get(id=event.event.broadcaster_user_id)

    if not channel:
        logger.error(f"A Stream Online Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
        return
    
    logger.info(f'{channel.name} has gone live!')

    await _download_stream(channel)


# Callback for when the webhook receives an offline event
async def _on_offline(event: StreamOfflineEvent):

    channel = await TwitchChannel.get(id=event.event.broadcaster_user_id)

    if not channel:
        logger.error(f"A Stream Offline Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
        return

    logger.info(f'{channel.name} has gone offline')


# Callback for when the webhook receives an update event
async def _on_update(event: ChannelUpdateEvent):

    channel = await TwitchChannel.get(id=event.event.broadcaster_user_id)

    if not channel:
        logger.error(f"A Channel Update Event was received for {event.event.broadcaster_user_name}, but it does not exist within the database. Discarding...")
        return

    logger.info(f'{event.event.broadcaster_user_name} has updated its information')

    update = TwitchChannelUpdate(
        id=uuid4().__str__(),
        channel=channel.id,
        timestamp=datetime.now(timezone.utc),
        title=event.event.title,
        category_name=event.event.category_name,
        category_id=event.event.category_id
    )
    await update.save()


# Function to download stream from a Twitch Channel
async def _download_stream(channel: TwitchChannel):

    logger.info(f'Grabbing stream info from {channel.name}')

    stream_info = await channel.get_stream_info()

    twitch_stream = TwitchStream(
        id=stream_info.id,
        channel=channel.id,
        title=stream_info.title,
        category_id=stream_info.game_id,
        category_name=stream_info.game_name,
        started_at=stream_info.started_at
    )
    await twitch_stream.save()
    
    path = channel.get_path()
    if not path.exists():
        path.mkdir()

    logger.info(f'Downloading stream from {channel.name} to {path}')

    # Use the async download function directly
    end_time = await _download_async(channel, twitch_stream, path)

    await twitch_stream.end(end_time)

    logger.info(f'Finished downloading stream from {channel.name} to {path}')


# Internal async function for downloading stream
async def _download_async(channel: TwitchChannel, twitch_stream: TwitchStream, path: Path):
    """Async wrapper for the download process"""
    
    buffer = None
    video_file = None
    
    try:
        # Initialize the first variables for the recording loops
        part = 1
        video_stream = channel.get_video_stream()
        buffer = video_stream.open()
        data = buffer.read(CHUNK_SIZE)
        
        # First loop for iterating through video files
        while data:
            # Create video file
            start = buffer.worker.playlist_sequence_last
            video_path = path.joinpath(
                NAMING_SCHEME.format(
                    channel=channel.login,
                    title=twitch_stream.title,
                    stream=twitch_stream.id,
                    part=part,
                    ext=VIDEO_EXTENSION
                )
            )
            video_file = VideoFile(
                id=uuid4().__str__(),
                stream=twitch_stream.id,
                channel=channel.id,
                quality=channel.quality,
                path=video_path,
                started_at=datetime.now(timezone.utc),
            )
            await video_file.save()

            logger.info(f'Writing stream from {channel.name} to {video_path}')

            # Write video chunks with proper cancellation support
            loop = asyncio.get_event_loop()
            
            def write_video_chunk():
                nonlocal data
                with open(video_path, 'wb') as file:
                    # Second loop for writing video stream data to file
                    while data:
                        file.write(data)
                        data = buffer.read(CHUNK_SIZE)
                        
                        # Check if the video has exceeded the cutoff and trigger next file if it does
                        if buffer.worker.playlist_sequence_last - start > CUTOFF:
                            logger.info(f'Video file {video_path} has reached the cutoff. Handing stream over to next file...')
                            return True  # Signal to break to next file
                    return False  # Signal that stream ended
            
            try:
                should_continue = await loop.run_in_executor(None, write_video_chunk)
            except asyncio.CancelledError:
                logger.info(f"Download cancelled for {channel.name}")
                # Cleanup partial file if needed
                if video_path.exists():
                    logger.info(f"Cleaning up partial file: {video_path}")
                raise  # Re-raise to properly handle cancellation
            
            if should_continue:
                await video_file.end()
                await transcode_queue.put(video_file)
                part = part + 1
            else:
                # Stream ended, break out of main loop
                break
                
    except asyncio.CancelledError:
        logger.info(f"Download cancelled for {channel.name}")
        raise  # Re-raise to properly handle cancellation
    except Exception as e:
        logger.error(f"Error during download for {channel.name}: {e}")
    finally:
        # Cleanup resources
        if buffer:
            try:
                buffer.close()
            except Exception as e:
                logger.error(f"Error closing buffer: {e}")
        
        # End the last video being written to if it exists
        if 'video_file' in locals() and video_file:
            try:
                end_time = datetime.now(timezone.utc)
                await video_file.end(end_time)
                await transcode_queue.put(video_file)
            except Exception as e:
                logger.error(f"Error finalizing video file: {e}")

    return datetime.now(timezone.utc)


# Internal function for downloading stream in executor (legacy sync wrapper)
def _download(channel: TwitchChannel, twitch_stream: TwitchStream, path: Path):
    """Sync wrapper that runs the async download function"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_download_async(channel, twitch_stream, path))
    finally:
        loop.close()
