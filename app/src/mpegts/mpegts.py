from pathlib import Path


class MPEGTSFile():

    def __init__(self, path: Path|str):
        self.path = Path(path)
        self._reader = open(self.path, 'rb')
        self.index_packets()

    def index_packets(self):
        self.index = []

        return self.index
