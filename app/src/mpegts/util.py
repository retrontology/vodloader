from io import BufferedReader

class MPEGTSLayer():

    _reader: BufferedReader
    _start: int

    def __init__(self, reader: BufferedReader):
        self._reader = reader
        self._start = self._reader.tell()
        self.parse()
    
    def parse(self):
        self._reader.seek(self._start)
        self._parse()

    def _parse(self):
        pass

    @staticmethod
    def mask(data: bytes, mask: int) -> int:
        
        data: int = int.from_bytes(data, byteorder='big')
        
        while not mask & 1:
            data = data >> 1
            mask = mask >> 1
        
        return data & mask
