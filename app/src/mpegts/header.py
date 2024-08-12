from .util import MPEGTSLayer
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

class PacketHeader(MPEGTSLayer):

    TEI: bool
    PUSI: bool
    TP: bool
    PID: int
    TSC: TransportScramblingControl
    AFC: AdaptationFieldControl

    def _parse(self):

        data = self._reader.read(HEADER_SIZE)
        
        sync = self.mask(data, MASK_SYNC)
        if sync != SYNC_BYTE:
            raise SyncByteMismatch
        
        self.TEI = bool(self.mask(data, MASK_TEI))
        self.PUSI = bool(self.mask(data, MASK_PUSI))
        self.TP = bool(self.mask(data, MASK_TP))
        self.PID = self.mask(data, MASK_PID)
        self.TSC = TransportScramblingControl(self.mask(data, MASK_TSC))
        self.AFC = AdaptationFieldControl(self.mask(data, MASK_AFC))
        self.CC = self.mask(data, MASK_CC)
    
    def __sizeof__(self) -> int:
        return HEADER_SIZE
    
class SyncByteMismatch(RuntimeError): pass
