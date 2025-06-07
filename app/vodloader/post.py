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
from datetime import timedelta, datetime


DEFAULT_WIDTH = 320
DEFAULT_FONT = "FreeSans"
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_COLOR = (0, 0, 0, 255)
DEFAULT_BACKGROUND_COLOR = (255, 255, 255, 0)



logger = logging.getLogger('vodloader.post')


async def remove_original(video: VideoFile):
    
    if not video.path:
        raise VideoAlreadyRemoved
    
    path = video.path
    video.path.unlink()
    video.path = None
    await video.save()
    logger.info(f'The original stream file at {path.__str__()} has been deleted')


async def transcode(video: VideoFile) -> None:

    if not video.ended_at:
        raise VideoFileNotEnded
    
    if video.transcode_path:
        raise VideoAlreadyTranscoded
    
    logger.info(f'Transcoding {video.path}')
    loop = asyncio.get_event_loop()
    video.transcode_path = await loop.run_in_executor(None, _transcode, video)
    await video.save()
    logger.info(f'Finished transcoding {video.path} to {video.transcode_path}')
    await remove_original(video)


def _transcode(video: VideoFile) -> Path:
    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    stream = ffmpeg.input(video.path.__str__())
    stream = ffmpeg.output(stream, transcode_path.__str__(), vcodec='copy')
    stream = ffmpeg.overwrite_output(stream)
    ffmpeg.run(stream, quiet=True)
    return transcode_path


async def generate_chat(
        video: VideoFile,
        width: int = DEFAULT_WIDTH,
        height: int = None,
        font_name: str = DEFAULT_FONT,
        font_size: int = DEFAULT_FONT_SIZE,
        font_color: str = DEFAULT_FONT_COLOR,
        background_color: str = DEFAULT_BACKGROUND_COLOR,
    ) -> None:

    logger.info(f'Generating chat video for {video.path}')

    font = None
    for font_obj in get_fonts():
        if font_obj.family_name == font_name:
            font = font_obj
            break
    if not font:
        raise ValueError(f'Font {font_name} not found')
    font = ImageFont.truetype(font.fname, font_size)

    messages = await Message.from_stream(video.stream)
    logger.info(f'Found {len(messages)} messages')

    video_in = cv2.VideoCapture(
        filename=video.path,
        apiPreference=cv2.CAP_FFMPEG,
        params={
            cv2.VIDEOWRITER_PROP_HW_ACCELERATION,
            cv2.VIDEO_ACCELERATION_ANY
        }
    )

    video_width = video_in.get(cv2.CAP_PROP_FRAME_WIDTH)
    video_height = video_in.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = video_in.get(cv2.CAP_PROP_FPS)

    chat_width = width
    chat_height = height if height else video_height
    line_height = font_size * 1.2

    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    video_out = cv2.VideoWriter(
        filename=transcode_path,
        apiPreference=cv2.CAP_FFMPEG,
        fourcc=cv2.VideoWriter_fourcc(*'mp4v'),
        fps=fps,
        frameSize=(video_width, video_height),
        params={
            cv2.VIDEOWRITER_PROP_HW_ACCELERATION,
            cv2.VIDEO_ACCELERATION_ANY
        }
    )

    start_x = 20
    start_y = 20
    max_y = chat_height - (start_y * 2)
    message_index = 0
    
    while True:

        ret, in_frame = video_in.read()
        if not ret:
            break

        time_offset = timedelta(milliseconds=video_in.get(cv2.CAP_PROP_POS_MSEC))
        current_time = video.started_at + time_offset

        while messages[message_index].timestamp <= current_time and message_index < len(messages):
            message_index += 1

        y = start_y

        visible_message_index = message_index
        while visible_message_index > 0 and y < max_y:
            message = messages[visible_message_index]
            draw.text((start_x, y), message.content, font=font, fill=font_color)
            y += line_height
            visible_message_index -= 1

        base_image = Image.fromarray(in_frame, mode="RGB")
        draw = ImageDraw.Draw(base_image)
        out_frame = cv2.cvtColor(np.array(base_image), cv2.COLOR_RGB2BGR)
        video_out.write(np.array(out_frame))
    
    video_in.release()
    video_out.release()
    


def get_fonts() -> List[FT2Font]:
    systemt_fonts = font_manager.findSystemFonts(fontext='ttf')
    fonts = []
    for font in systemt_fonts:
        try:
            fonts.append(font_manager.get_font(font))
        except Exception as e:
            print(f'Ran into the following exception trying to load the font from {font}: {e}')
    return fonts


async def transcode_loop():
    while True:
        video = await VideoFile.get_next_transcode()
        if video:
            await transcode(video)
        else:
            await asyncio.sleep(60)


class VideoAlreadyTranscoded(Exception): pass
class VideoAlreadyRemoved(Exception): pass
class VideoFileNotEnded(Exception): pass
