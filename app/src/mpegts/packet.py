from .util import MPEGTSLayer
from .header import PacketHeader
from .adaptation import PacketAdapatationField
from .payload import PacketPayload

class Packet(MPEGTSLayer):

    header: PacketHeader
    adaptation: PacketAdapatationField
    payload: PacketPayload
    
    def _parse(self):
        self.header = PacketHeader(self._reader)
