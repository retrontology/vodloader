from .util import MPEGTSLayer

PCR_LENGTH = 6

MASK_BASE      = 0xffffffff8000
MASK_RESERVED  = 0x000000007e00
MASK_EXTENSION = 0x0000000001ff

class ProgramClockReference(MPEGTSLayer):

    def _parse(self):
        
        data = self._reader.read(PCR_LENGTH)

        base = self.mask(data, MASK_BASE)
        extension = self.mask(data, MASK_EXTENSION)

        self.value = base * 300 + extension
    
    def __sizeof__(self) -> int:
        return PCR_LENGTH
