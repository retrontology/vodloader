"""
Video transcoding functionality for Twitch VODs.

This module handles basic video transcoding operations including:
- Converting video files to MP4 format
- Managing transcoding queues
- File cleanup operations
"""

import ffmpeg
import asyncio
import logging
from pathlib import Path
from typing import Optional

from vodloader.models import VideoFile

logger = logging.getLogger('vodloader.post.transcoding')

# Global transcoding queue
transcode_queue = asyncio.Queue()


class VideoAlreadyTranscoded(Exception):
    """Raised when attempting to transcode an already transcoded video."""
    pass


class VideoAlreadyRemoved(Exception):
    """Raised when attempting to remove an already removed video."""
    pass


class VideoFileNotEnded(Exception):
    """Raised when attempting to transcode a video that hasn't ended."""
    pass


async def remove_original(video: VideoFile) -> None:
    """
    Removes the original stream file from the system.
    
    Args:
        video: The video file to remove the original from
        
    Raises:
        VideoAlreadyRemoved: If the video path is already None
    """
    if not video.path:
        raise VideoAlreadyRemoved("Video path is already None")
    
    path = video.path
    video.path.unlink()
    video.path = None
    await video.save()
    logger.info(f'The original stream file at {path} has been deleted')


async def transcode(video: VideoFile) -> Path:
    """
    Transcode a video file to MP4 format.
    
    Args:
        video: The video file to transcode
        
    Returns:
        Path to the transcoded file
        
    Raises:
        VideoFileNotEnded: If the video hasn't ended yet
        VideoAlreadyTranscoded: If the video is already transcoded
    """
    if not video.ended_at:
        raise VideoFileNotEnded("Cannot transcode video that hasn't ended")
    
    if video.transcode_path:
        raise VideoAlreadyTranscoded("Video is already transcoded")
    
    logger.info(f'Transcoding {video.path}')

    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    
    # Run ffmpeg in executor to avoid blocking
    loop = asyncio.get_event_loop()
    
    def run_ffmpeg():
        stream = ffmpeg.input(str(video.path))
        stream = ffmpeg.output(stream, str(transcode_path), vcodec='copy')
        stream = ffmpeg.overwrite_output(stream)
        ffmpeg.run(stream, quiet=True)
    
    await loop.run_in_executor(None, run_ffmpeg)
    
    video.transcode_path = transcode_path
    await video.save()
    
    logger.info(f'Successfully transcoded {video.path} to {transcode_path}')
    return video.transcode_path


async def transcode_listener():
    """
    Listen for videos to transcode and process them.
    
    This function runs continuously, processing videos from the transcode queue.
    It will attempt to generate chat videos first, falling back to regular
    transcoding if no chat messages are found.
    
    This function is designed to be resilient and will never exit unless
    explicitly cancelled, ensuring the transcoding service stays running
    even if individual videos fail to process.
    """
    logger.info("Starting transcode listener")
    
    # Import here to avoid circular imports
    from .chat_video import generate_chat_video
    
    consecutive_errors = 0
    max_consecutive_errors = 10
    base_retry_delay = 1
    max_retry_delay = 60
    
    while True:
        try:
            # Reset error counter on successful loop iteration
            consecutive_errors = 0
            
            try:
                # Use timeout to allow for graceful shutdown
                video = await asyncio.wait_for(transcode_queue.get(), timeout=1.0)
                
                try:
                    logger.info(f"Processing video {video.id} for transcoding")
                    
                    # Try to generate chat video first (includes transcoding)
                    result = await generate_chat_video(video)
                    if result is not None:
                        logger.info(f"Successfully generated chat video for {video.id}")
                    else:
                        # No messages found, fall back to regular transcoding
                        logger.info(f"No chat messages found for video {video.id}, performing regular transcode")
                        await transcode(video)
                        logger.info(f"Successfully transcoded video {video.id}")
                        
                except Exception as e:
                    logger.error(f"Error processing video {video.id}: {e}")
                finally:
                    transcode_queue.task_done()
                    
            except asyncio.TimeoutError:
                # Timeout allows for graceful shutdown checks
                continue
                
        except asyncio.CancelledError:
            logger.info("Transcode listener cancelled")
            break
        except Exception as e:
            consecutive_errors += 1
            retry_delay = min(base_retry_delay * (2 ** consecutive_errors), max_retry_delay)
            
            logger.error(f"Critical error in transcode listener (attempt {consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive errors ({consecutive_errors}), using maximum retry delay")
                retry_delay = max_retry_delay
            
            logger.info(f"Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)


async def queue_trancodes():
    """
    Queue all non-transcoded videos for processing.
    
    This function fetches all videos that haven't been transcoded yet
    and adds them to the processing queue. It's designed to be resilient
    and will not raise exceptions that could crash the application.
    """
    try:
        logger.info("Queuing non-transcoded videos for processing...")
        videos = await VideoFile.get_nontranscoded()
        
        # Convert to list if it's a generator to get length
        if hasattr(videos, '__aiter__'):
            # It's an async generator
            video_list = []
            queued_count = 0
            async for video in videos:
                try:
                    video_list.append(video)
                    await transcode_queue.put(video)
                    queued_count += 1
                except Exception as e:
                    logger.error(f"Failed to queue video {getattr(video, 'id', 'unknown')}: {e}")
            
            logger.info(f"Successfully queued {queued_count} of {len(video_list)} videos for transcoding")
        else:
            # It's a regular iterable, convert to list
            video_list = list(videos)
            logger.info(f"Found {len(video_list)} videos to queue for transcoding")
            
            queued_count = 0
            for video in video_list:
                try:
                    await transcode_queue.put(video)
                    queued_count += 1
                except Exception as e:
                    logger.error(f"Failed to queue video {getattr(video, 'id', 'unknown')}: {e}")
            
            logger.info(f"Successfully queued {queued_count} of {len(video_list)} videos for transcoding")
            
    except Exception as e:
        logger.error(f"Critical error while queueing transcodes: {e}")
        logger.info("Transcoding queue initialization failed, but service will continue running")


async def get_queue_size() -> int:
    """
    Get the current size of the transcode queue.
    
    Returns:
        Number of videos waiting to be processed
    """
    return transcode_queue.qsize()


async def clear_queue():
    """Clear all items from the transcode queue."""
    while not transcode_queue.empty():
        try:
            transcode_queue.get_nowait()
            transcode_queue.task_done()
        except asyncio.QueueEmpty:
            break
    logger.info("Transcode queue cleared")