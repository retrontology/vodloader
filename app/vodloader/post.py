from vodloader.models import VideoFile, Message
import ffmpeg
import cv2
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font
from typing import List
from pathlib import Path
import asyncio
import logging
from datetime import timedelta


DEFAULT_WIDTH = 320
DEFAULT_FONT_FAMILY = "FreeSans"
DEFAULT_FONT_STYLE = "Regular"
DEFAULT_FONT_SIZE = 24
DEFAULT_FONT_COLOR = (255, 255, 255, 255)
DEFAULT_BACKGROUND_COLOR = (0, 0, 0, 127)
DEFAULT_MESSAGE_DURATION = 10


transcode_queue = asyncio.Queue()
logger = logging.getLogger('vodloader.post')


async def remove_original(video: VideoFile):
    """
    Removes the original stream file from the system
    """
    
    if not video.path:
        raise VideoAlreadyRemoved
    
    path = video.path
    video.path.unlink()
    video.path = None
    await video.save()
    logger.info(f'The original stream file at {path.__str__()} has been deleted')


def transcode(video: VideoFile) -> Path:
    """
    Synchronous function to transcode a video file to mp4

    Args:
        video (VideoFile): The video file to transcode.
    Returns:
        Path: The path to the transcoded file.
    """
    if not video.ended_at:
        raise VideoFileNotEnded
    
    if video.transcode_path:
        raise VideoAlreadyTranscoded
    
    logger.info(f'Transcoding {video.path}')

    loop = asyncio.new_event_loop()

    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    stream = ffmpeg.input(video.path.__str__())
    stream = ffmpeg.output(stream, transcode_path.__str__(), vcodec='copy')
    stream = ffmpeg.overwrite_output(stream)
    ffmpeg.run(stream, quiet=True)
    video.transcode_path = transcode_path
    loop.run_until_complete(video.save())
    loop.run_until_complete(remove_original(video))

    return video.transcode_path


def generate_chat_video(
        video: VideoFile,
        width: int = DEFAULT_WIDTH,
        height: int = None,
        font_family: str = DEFAULT_FONT_FAMILY,
        font_style: str = DEFAULT_FONT_STYLE,
        font_size: int = DEFAULT_FONT_SIZE,
        font_color: str = DEFAULT_FONT_COLOR,
        background_color: str = DEFAULT_BACKGROUND_COLOR,
        message_duration: int = DEFAULT_MESSAGE_DURATION
    ) -> Path:
    """
    Transcodes a stream and overlays chat messages on it.

    Args:
        video (VideoFile): The video to transcode.
        width (int): The width of the output video.
        height (int): The height of the output video.
        font_family (str): The font family to use.
        font_style (str): The font style to use.
        font_size (int): The font size to use.
        font_color (str): The font color to use.
        background_color (str): The background color to use.
        message_duration (int): The duration of each message in seconds.
    Returns:
        Path: The path to the transcoded video.
    Raises:
        Exception: If an error occurs during transcoding.
    """

    loop = asyncio.new_event_loop()

    logger.info(f'Generating chat video for {video.path}')

    # Convert the message duration for easier handling
    message_duration = timedelta(seconds=message_duration)

    # Get the messages for this video
    message_index = 0
    messages = loop.run_until_complete(Message.for_video(video))
    if len(messages) == 0:
        logger.info('No messages found for this video')
        return None
    logger.info(f'Found {len(messages)} messages')

    # Trim the input video
    #ffmpeg -ss 00:00:30 -i input.mp4 -c copy output.mp4
    trim_path = video.path.parent.joinpath(f'{video.path.stem}.trim.ts')
    trim_video = ffmpeg.input(video.path.__str__(), ss=30)
    trim_video = ffmpeg.output(trim_video, trim_path.__str__(), codec='copy')
    trim_video = ffmpeg.overwrite_output(trim_video)
    ffmpeg.run(trim_video, quiet=True)

    # Load the font
    logger.debug('Loading the font...')
    font = get_font(font_family, font_style, font_size)

    # Open the input video file
    logger.debug('Opening the trimmed stream file...')
    video_in = cv2.VideoCapture(
        filename=trim_path,
        apiPreference=cv2.CAP_FFMPEG
    )

    # Read properties of the input video file
    logger.debug('Reading the properties of the original stream video...')
    video_width = video_in.get(cv2.CAP_PROP_FRAME_WIDTH)
    video_height = video_in.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = video_in.get(cv2.CAP_PROP_FPS)

    # Calculate chat dimensions
    chat_width = width
    chat_height = height if height else video_height
    line_height = font_size * 1.2
    start_x = 20
    start_y = 20
    max_y = chat_height - (start_y * 2)

    # Open the output file
    logger.debug('Opening the output chat video file...')
    chat_video_path = video.path.parent.joinpath(f'{video.path.stem}.chat.mp4')
    video_out = cv2.VideoWriter(
        filename=chat_video_path,
        fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
        fps=fps,
        frameSize=(int(video_width), int(video_height))
    )
    
    # Loop through each frame
    while True:

        # Read a new frame from the stream
        ret, in_frame = video_in.read()
        if not ret:
            break
        base_image = Image.fromarray(in_frame, mode="RGB")
        draw = ImageDraw.Draw(base_image)

        # Calculate the current time in the stream
        time_offset = timedelta(milliseconds=video_in.get(cv2.CAP_PROP_POS_MSEC))
        current_time = video.started_at + time_offset

        # Point the index to the newest message for the current frame
        while messages[message_index].timestamp <= current_time:
            if message_index >= len(messages) - 1:
                break
            if messages[message_index+1].timestamp > current_time:
                break
            message_index += 1

        # Iterate through visible messages
        current_y = start_y
        visible_message_index = message_index
        while True:
            if current_y > max_y:
                break
            message = messages[visible_message_index]
            if (current_time - message.timestamp) > message_duration:
                break

            prefix = f'{message.display_name}:'

            # Break the message into lines and calculate their positions
            words = message.content.split(' ')
            lines = [[]]
            temp_x = start_x + draw.textlength(prefix, font=font)
            for word in words:
                word_length = draw.textlength(f' {word}', font=font)
                if temp_x + word_length > chat_width:
                    lines.append([word])
                    temp_x = start_x + draw.textlength(word, font=font)
                else:
                    lines[-1].append(word)
                    temp_x += word_length

            # If the message is too big to fit, exit before drawing it
            if len(lines) * line_height + current_y > max_y:
                break

            # Draw the message
            draw.text((start_x, current_y), prefix, font=font, fill=message.color, stroke_fill=background_color, stroke_width=2)
            current_x = start_x + draw.textlength(f'{prefix} ', font=font)
            for line in lines:
                if not line:
                    continue
                line = ' '.join(line)
                draw.text((current_x, current_y), line, font=font, fill=font_color)
                current_y += line_height
                current_x = start_x

            # Decrement the visible message index
            if visible_message_index > 0:
                visible_message_index -= 1
            else:
                break

        # Write the frame to the output video
        video_out.write(np.array(base_image))
    
    # Release both input and output video files
    logger.debug('Releasing the video files...')
    video_in.release()
    video_out.release()
    trim_path.unlink()

    # Mux the audio and video streams while transcoding the audio
    logger.debug('Muxing the chat video with transcoded audio...')
    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    chat_stream = ffmpeg.input(chat_video_path.__str__())
    original_stream = ffmpeg.input(video.path.__str__())
    output_stream = ffmpeg.output(chat_stream['v:0'], original_stream['a:0'], transcode_path.__str__(), vcodec='copy', acodec='aac')
    output_stream = ffmpeg.overwrite_output(output_stream)
    ffmpeg.run(output_stream, quiet=True)

    # Set the transcode path in the model
    video.transcode_path = transcode_path
    loop.run_until_complete(video.save())

    # Remove the chat and original video files
    chat_video_path.unlink()
    #remove_original(video)

    # Return the path of the transcoded video file
    return transcode_path


def get_fonts() -> List[FT2Font]:
    """
    Returns a list of all available fonts on the system.

    Returns:
        List[FT2Font]:
            A list of all available fonts on the
    """
    systemt_fonts = font_manager.findSystemFonts(fontext='ttf')
    fonts = []
    for font in systemt_fonts:
        try:
            fonts.append(font_manager.get_font(font))
        except Exception as e:
            print(f'Ran into the following exception trying to load the font from {font}: {e}')
    return fonts


def get_font(
        font_family: str = DEFAULT_FONT_FAMILY,
        font_style: str = DEFAULT_FONT_STYLE,
        font_size: int = DEFAULT_FONT_SIZE,
) -> ImageFont.FreeTypeFont:
    """
    Returns a font object for the specified font family, style, and size.

    Args:
        font_family (str, optional): The font family to use. Defaults to DEFAULT_FONT_FAMILY.
        font_style (str, optional): The font style to use. Defaults to DEFAULT_FONT_STYLE.
        font_size (int, optional): The font size to use. Defaults to DEFAULT_FONT_SIZE.
    Returns:
        ImageFont.FreeTypeFont: A font object for the specified font family, style, and size.
    Raises:
        ValueError: If the specified font is not found.
    """
    font = None
    for font_obj in get_fonts():
        if font_obj.family_name == font_family and font_obj.style_name == font_style:
            font = font_obj
            break
    if not font:
        raise ValueError(f'Font {font_family} {font_style} not found')
    return ImageFont.truetype(font.fname, font_size)


async def transcode_listener():
    loop = asyncio.get_event_loop()
    while True:
        video = await transcode_queue.get()
        result = await loop.run_in_executor(None, generate_chat_video, video)
        if result == None:
            await loop.run_in_executor(None, transcode, video)


async def queue_trancodes():
    videos = await VideoFile.get_nontranscoded()
    for video in videos:
        await transcode_queue.put(video)


class VideoAlreadyTranscoded(Exception): pass
class VideoAlreadyRemoved(Exception): pass
class VideoFileNotEnded(Exception): pass
