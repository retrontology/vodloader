from vodloader.post import generate_chat_video
from vodloader.models import VideoFile
import asyncio


async def app():
    loop = asyncio.get_event_loop()
    video = await VideoFile.get(id='3f6db9ee-b7bc-4784-a38e-1fc7a2adfa56')
    loop.run_in_executor(None, generate_chat_video, video)


if __name__ == '__main__':
    asyncio.run(app())
