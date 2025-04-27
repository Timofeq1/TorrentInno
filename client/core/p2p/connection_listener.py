from core.p2p.message import Request, Piece, Bitfield


class ConnectionListener:
    async def on_request(self, request: Request):
        pass

    async def on_piece(self, piece: Piece):
        pass

    async def on_bitfield(self, bitfield: Bitfield):
        pass

    def on_close(self, cause):
        pass
