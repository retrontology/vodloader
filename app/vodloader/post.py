from vodloader.models import VideoFile
import ffmpeg
import cv2
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font
from typing import List
from pathlib import Path
import asyncio


DEFAULT_WIDTH = 320


async def remove_original(video: VideoFile):
    
    if not video.path:
        raise VideoAlreadyRemoved
    
    path = video.path
    video.path.unlink()
    video.path = None
    await video.save()
    video.logger.info(f'The original stream file at {path.__str__()} has been deleted')


async def transcode(video: VideoFile) -> None:

    if not video.ended_at:
        raise VideoFileNotEnded
    
    if video.transcode_path:
        raise VideoAlreadyTranscoded
    
    video.logger.info(f'Transcoding {video.path}')
    loop = asyncio.get_event_loop()
    video.transcode_path = await loop.run_in_executor(None, _transcode, video)
    await video.save()
    video.logger.info(f'Finished transcoding {video.path} to {video.transcode_path}')
    await remove_original(video)


def _transcode(video: VideoFile) -> Path:
    transcode_path = video.path.parent.joinpath(f'{video.path.stem}.mp4')
    stream = ffmpeg.input(video.path.__str__())
    stream = ffmpeg.output(stream, transcode_path.__str__(), vcodec='copy')
    stream = ffmpeg.overwrite_output(stream)
    ffmpeg.run(stream, quiet=True)
    return transcode_path


def _get_fonts() -> List[FT2Font]:
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
