import logging
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
from functools import partial
from vodloader.models import *
from vodloader.twitch import twitch, webhook
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent, ChannelUpdateEvent


CHUNK_SIZE = 8192
MAX_VIDEO_LENGTH = 60*(60*12-15)
VIDEO_EXTENSION = 'ts'
MAX_LENGTH=60*(60*12-15)


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
async def _on_update(self, event: ChannelUpdateEvent):

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

    name = f'{stream_info.user_login}-{stream_info.title}-{stream_info.id}.{VIDEO_EXTENSION}'
    path = Path(config.DOWNLOAD_DIR).joinpath(name)

    logger.info(f'Downloading stream from {channel.name} to {path}')

    video_file = VideoFile(
        id=uuid4().__str__(),
        stream=stream_info.id,
        channel=channel.id,
        quality=channel.quality,
        path=path,
        started_at=datetime.now(timezone.utc),
    )
    await video_file.save()

    loop = asyncio.get_event_loop()
    download_function = partial(_download, channel=channel, path=path)
    await loop.run_in_executor(None, download_function)

    end_time = datetime.now(timezone.utc)
    await twitch_stream.end(end_time)
    await video_file.end(end_time)

    logger.info(f'Finished downloading stream from {channel.name} to {path}')


# Internal function for downloading stream in executor
def _download(channel: TwitchChannel, path:Path):
    stream = channel.get_video_stream()
    buffer = stream.open()
    with open(path, 'wb') as f:
        try:
            data = buffer.read(CHUNK_SIZE)
            while data:
                f.write(data)
                data = buffer.read(CHUNK_SIZE)
        except Exception as e:
            logger.error(e)
    buffer.close()
