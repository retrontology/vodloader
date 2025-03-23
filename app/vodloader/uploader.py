import io
import ffmpeg
import subprocess
from googleapiclient.http import MediaIoBaseUpload

DEFAULT_CHUNK_SIZE=188
MAX_LENGTH=60*(60*12-15)
DEFAULT_LENGTH = 60*60*8

class MediaSplitUpload(MediaIoBaseUpload):

    def __init__(
        self,
        file,
        part=1,
        mimetype="application/octet-stream",
        chunksize=DEFAULT_CHUNK_SIZE,
        resumable=True,
    ):
        self.start = DEFAULT_LENGTH * (part - 1) - 60 * (part - 1)
        self.length = DEFAULT_LENGTH
        args = (
            ffmpeg
            .input(file, ss=self.start, t=self.length)
            .output('pipe:', format='mpegts', vcodec='copy', acodec='copy')
            .compile()
        )
        body = subprocess.Popen(args, stdout=subprocess.PIPE)
        super().__init__(
            body, mimetype, chunksize=chunksize, resumable=resumable
        )
