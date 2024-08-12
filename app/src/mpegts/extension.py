from .util import MPEGTSLayer


EXTENSION_SIZE = 2
LEGAL_TIME_WINDOW_SIZE = 2
PIECEWISE_RATE_SIZE = 3
MASK_SEAMLESS_SPLICE = 5

MASK_EXTENSION_LENGTH  = 0xff00
MASK_LEGAL_TIME_WINDOW = 0x0080
MASK_PIECEWISE_RATE    = 0x0040
MASK_SEAMLESS_SPLICE   = 0x0020
MASK_RESERVED          = 0x001f

MASK_LTW_VALID  = 0x8000
MASK_LTW_OFFSET = 0x7fff

MASK_PIECEWISE_RESERVED = 0xc00000
MASK_PIECEWISE_RATE     = 0x3fffff

MASK_SPLICE_TYPE = 0xf000000000
MASK_SPLICE_DTS  = 0x0efffefffe


class LegalTimeWindow(MPEGTSLayer):

    valid: bool
    offset: int

    def _parse(self):
        data = self._reader.read(LEGAL_TIME_WINDOW_SIZE)
        self.valid = bool(self.mask(data, MASK_LTW_VALID))
        self.offset = self.mask(data, MASK_LTW_OFFSET)

class PiecewiseRate(MPEGTSLayer):

    rate: int
    
    def _parse(self):
        data = self._reader.read(PIECEWISE_RATE_SIZE)
        self.rate = self.mask(data, MASK_PIECEWISE_RATE)

class SeamlessSplice(MPEGTSLayer):

    type: int
    dts: int

    def _parse(self):
        data = self._reader.read(MASK_SEAMLESS_SPLICE)
        self.type = self.mask(data, MASK_SPLICE_TYPE)
        self.dts = MASK_SPLICE_DTS

class PacketAdapatationExtension(MPEGTSLayer):

    def _parse(self):

        data = self._reader.read(EXTENSION_SIZE)

        self.length = self.mask(data, MASK_EXTENSION_LENGTH)
        legal_time_window = self.mask(data, MASK_LEGAL_TIME_WINDOW)
        piecewise_rate = self.mask(data, MASK_PIECEWISE_RATE)
        seamless_splice = self.mask(data, MASK_SEAMLESS_SPLICE)

        if legal_time_window:
            self.legal_time_window = LegalTimeWindow(self._reader)
        else:
            self.legal_time_window = None
        
        if piecewise_rate:
            self.piecewise_rate = PiecewiseRate(self._reader)
        else:
            self.piecewise_rate = None

        if seamless_splice:
            self.seamless_splice = SeamlessSplice(self._reader)
        else:
            self.seamless_splice = None