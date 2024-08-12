from .util import MPEGTSLayer
from .pcr import ProgramClockReference
from .private import PacketPrivateData
from .extension import PacketAdapatationExtension

ADAPTATION_SIZE = 1
SPLICE_SIZE = 1

MASK_DISCONTINUITY = 0x80
MASK_RANDOM_ACCESS = 0x40
MASK_PRIORITY      = 0x20
MASK_PCR           = 0x10
MASK_OPCR          = 0x08
MASK_SPLICING      = 0x04
MASK_PRIVATE       = 0x02
MASK_EXTENSION     = 0x01

class PacketAdapatationField(MPEGTSLayer):

    discontinuity: bool
    random_access: bool
    priority: bool
    pcr: int | None
    opcr: int | None
    splice: int | None
    private: PacketPrivateData | None
    extension: PacketAdapatationExtension | None
    
    def _parse(self):

        data = self._reader.read(ADAPTATION_SIZE)
        data = int.from_bytes(data)

        self.discontinuity = bool(data & MASK_DISCONTINUITY)
        self.random_access = bool(data & MASK_RANDOM_ACCESS)
        self.priority = bool(data & MASK_PRIORITY)
        pcr = bool(data & MASK_PCR)
        opcr = bool(data & MASK_OPCR)
        splice = bool(data & MASK_SPLICING)
        private = bool(data & MASK_PRIVATE)
        extension = bool(data & MASK_EXTENSION)

        if pcr:
            self.pcr = ProgramClockReference(self._reader)
        else:
            self.pcr = None
        
        if opcr:
            self.opcr = ProgramClockReference(self._reader)
        else:
            self.opcr = None

        if splice:
            data = self._reader.read(SPLICE_SIZE)
            self.splice = int.from_bytes(data, 'big', True)
        else:
            self.splice = None

        if private:
            self.private = PacketPrivateData(self._reader)
            end = self.private._start + len(self.private)
            self._reader.seek(end)
        else:
            self.private = None

        if extension:
            self.extension = PacketAdapatationExtension(self._reader)
        else:
            self.extension = None

    def __sizeof__(self) -> int:
        length = ADAPTATION_SIZE
        if self.pcr:
            length += len(self.pcr)
        if self.opcr:
            length += len(self.opcr)
        if self.splice != None:
            length += SPLICE_SIZE
        if self.private:
            length += len(self.private)
        if self.extension:
            length += len(self.extension)
        return length
