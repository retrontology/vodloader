from pathlib import Path
from .packet import *


class MPEGTSFile():

    def __init__(self, path: Path|str):
        self.path = Path(path)
        self._reader = open(self.path, 'rb')

    def parse(self):
        
        self.packets = []
        offset = 0
        while True:
            self._reader.seek(offset)
            try:
                self.packets.append(Packet(self._reader))
            except Exception as e:
                print(e)
                break
            offset += PACKET_SIZE
