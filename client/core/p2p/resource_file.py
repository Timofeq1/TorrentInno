from pathlib import Path

from core.common.resource import Resource


class ResourceFile:
    def __init__(self, destination: Path, resource: Resource):
        self.file = destination
        self.resource = resource

    async def get_piece(self, index: int) -> bytes:
        return await self.get_block(index, 0, self.resource.pieces[index].size_bytes)

    async def get_block(self, piece_index: int, piece_inner_offset: int, block_length: int) -> bytes:
        pass

    async def save_block(self, piece_index: int, piece_inner_offset: int, data: bytes):
        pass

    async def save_validated_piece(self, index: int, data: bytes):
        pass

    async def prepare(self):
        pass