from .util import MPEGTSLayer
from .header import PacketHeader
from .adaptation import PacketAdapatationField
from .payload import PacketPayload

PACKET_SIZE = 188

class Packet(MPEGTSLayer):

    header: PacketHeader
    adaptation: PacketAdapatationField
    payload: PacketPayload
    
    def _parse(self):
        self.header = PacketHeader(self._reader)
