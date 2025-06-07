from vodloader.post import generate_chat
from vodloader.models import VideoFile


async def app():
    video = await VideoFile.get(id='991f6eaf-5373-4b5c-a106-87d4853fcba0')
    await generate_chat(video)


if __name__ == '__main__':
    import asyncio
    asyncio.run(app())
