from vodloader.post import generate_chat_video
from vodloader.models import VideoFile


async def app():
    #video = await VideoFile.get(id='52dc83aa-98e9-4e46-8f9e-d6ac8daf39ac')
    #await generate_chat_video(video)
    videos = await VideoFile.get_nontranscoded()
    print(videos)


if __name__ == '__main__':
    import asyncio
    asyncio.run(app())
