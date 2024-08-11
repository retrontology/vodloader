from pathlib import Path
from io import BufferedReader
from enum import Enum

SYNC_BYTE = int.from_bytes(b'G')
HEADER_SIZE = 4

MASK_SYNC = 0xff000000
MASK_TEI  = 0x00800000
MASK_PUSI = 0x00400000
MASK_TP   = 0x00200000
MASK_PID  = 0x001fff00
MASK_TSC  = 0x000000c0
MASK_AFC  = 0x00000030
MASK_CC   = 0x0000000f

class TransportScramblingControl(Enum):
    NOT_SCRAMBLED = 0
    RESERVED = 1
    SCRAMBLED_EVEN = 2
    SCRAMBLED_ODD = 3

class AdaptationFieldControl(Enum):
    RESERVED = 0
    PAYLOAD = 1
    ADAPTATION = 2
    ADAPTATION_PAYLOAD = 3


class MPEGTSFile():

    def __init__(self, path: Path|str):
        self.path = Path(path)
        self._reader = open(self.path, 'rb')
        self.index_packets()

    def index_packets(self):
        self.index = []

        return self.index


class PacketHeader():

    _start: int
    _len: int = HEADER_SIZE
    TEI: bool
    PUSI: bool
    TP: bool
    PID: int
    TSC: TransportScramblingControl
    AFC: AdaptationFieldControl


    def __init__(self, reader: BufferedReader) -> None:
        self._reader = reader
        self._start = self._reader.tell()
        self._parse()

    def _parse(self):

        self._reader.seek(self._start)
        data = self._reader.read(HEADER_SIZE)
        
        sync = self.mask_header(data, MASK_SYNC)
        if sync != SYNC_BYTE:
            raise SyncByteMismatch
        
        self.TEI = bool(self.mask_header(data, MASK_TEI))
        self.PUSI = bool(self.mask_header(data, MASK_PUSI))
        self.TP = bool(self.mask_header(data, MASK_TP))
        self.PID = self.mask_header(data, MASK_PID)
        self.TSC = TransportScramblingControl(self.mask_header(data, MASK_TSC))
        self.AFC = AdaptationFieldControl(self.mask_header(data, MASK_AFC))
        self.CC = self.mask_header(data, MASK_CC)
        
    
    @staticmethod
    def mask_header(data: bytes, mask: int) -> int:

        if len(data) != 4:
            raise InvalidMask
        
        data: int = int.from_bytes(data, byteorder='big')
        
        while not mask & 1:
            data = data >> 1
            mask = mask >> 1
        
        return data & mask

class PacketAdapatationExtension():
    pass

class PacketAdapatationField():
    
    extension: PacketAdapatationExtension = None

class PacketPayload():
    pass

class Packet():

    _start: int
    header: PacketHeader
    adaptation: PacketAdapatationField
    payload: PacketPayload

    def __init__(self, reader: BufferedReader) -> None:
        self._reader = reader
        self._start = self._reader.tell()
        self.parse()
    
    def parse(self):
        self.header = PacketHeader(self._reader)


class SyncByteMismatch(RuntimeError): pass
class InvalidMask(RuntimeError): pass