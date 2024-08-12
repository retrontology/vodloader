from .util import MPEGTSLayer

PRIVATE_HEADER_SIZE = 1

class PacketPrivateData(MPEGTSLayer):

    def _parse(self):
        data = self._reader.read(PRIVATE_HEADER_SIZE)
        self.length = int.from_bytes(data, 'big')
    
    def read(self) -> bytes:
        self._reader.seek(self._start+PRIVATE_HEADER_SIZE)
        return self._reader.read(self.length)

    def __sizeof__(self) -> int:
        return PRIVATE_HEADER_SIZE + self.length
