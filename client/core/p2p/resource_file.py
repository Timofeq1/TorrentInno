import asyncio
from itertools import accumulate
from pathlib import Path

import aiofiles
import aiofiles.os

from core.common.resource import Resource


class ResourceFile:
    """
    Class that represents the destination of resource. The main purpose of this class is to hide
    the complexities of managing the "hidden file" and the aiofiles-related operations. Everything else
    (checking and validating pieces, for example) is the caller's responsibility.

    There basically two operating modes:
    1) The destination file exists. Then this file will be used in all read operations. The write operations
    will raise RuntimeException.
    2) The destination file does not exist. Then the auxiliary downloading_destination file will be used.
    This file is created with the size of the initial destination file. When the client decides that all pieces
    are written, then it calls the accept_download and the file gets renamed to the original destination name.
    """

    def __init__(self, destination: Path, resource: Resource, fresh_install=True):
        self.destination = destination
        self.resource = resource
        self.downloading_destination = self.get_downloading_destination()
        self.lock = asyncio.Lock()

        if fresh_install:
            destination.unlink(missing_ok=True)
            self.downloading_destination.unlink(missing_ok=True)

        self.offsets: list[int] = [0] + list(accumulate(piece.size_bytes for piece in resource.pieces))

    def get_downloading_destination(self) -> Path:
        return self.destination.parent.joinpath(f'.torrentinno-{self.destination.name}')

    def _calculate_offset(self, piece_index: int, piece_inner_offset: int) -> int:
        return self.offsets[piece_index] + piece_inner_offset

    async def _create_downloading_destination(self):
        async with aiofiles.open(self.downloading_destination, mode='wb') as f:
            for piece in self.resource.pieces:
                await f.write(bytes([0] * piece.size_bytes))

    async def _ensure_downloading_destination(self):
        async with self.lock:
            if not self.downloading_destination.exists():
                await self._create_downloading_destination()

    async def get_piece(self, index: int) -> bytes:
        return await self.get_block(index, 0, self.resource.pieces[index].size_bytes)

    async def get_block(self, piece_index: int, piece_inner_offset: int, block_length: int) -> bytes:
        offset = self._calculate_offset(piece_index, piece_inner_offset)
        if offset + block_length > self.offsets[-1]:
            raise RuntimeError("The requested read portion does not fit the file")

        take_from: Path
        if self.destination.exists():
            take_from = self.destination
        else:
            await self._ensure_downloading_destination()
            take_from = self.downloading_destination

        async with aiofiles.open(take_from, mode='rb') as f:
            await f.seek(offset)
            return await f.read(block_length)

    async def save_block(self, piece_index: int, piece_inner_offset: int, data: bytes):
        offset = self._calculate_offset(piece_index, piece_inner_offset)
        if offset + len(data) > self.offsets[-1]:
            raise RuntimeError("The write portion overflows the file")

        if self.destination.exists():
            raise RuntimeError("File is already downloaded")

        await self._ensure_downloading_destination()

        async with aiofiles.open(self.downloading_destination, mode='r+b') as f:
            await f.seek(offset)
            await f.write(data)

    async def save_validated_piece(self, piece_index: int, data: bytes):
        await self.save_block(piece_index, 0, data)

    async def accept_download(self):
        await aiofiles.os.rename(self.downloading_destination, self.destination)
