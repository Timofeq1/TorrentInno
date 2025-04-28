import asyncio
from itertools import accumulate
from pathlib import Path

import aiofiles
import aiofiles.os

from core.common.resource import Resource
from enum import Enum


class ResourceFile:
    """
    Class that represents the destination of resource. The main purpose of this class is to hide
    the complexities of managing the "hidden file" and the aiofiles-related operations. Everything else
    (checking and validating pieces, for example) is the caller's responsibility.

    The class has two states
    1) Downloading state. In this state the temporary file is created and uses to write/read operations
    2) Downloaded state. In this state the destination itself is used to read operations. Write operations
    raise exception.
    """

    class State(Enum):
        DOWNLOADING = 1
        DOWNLOADED = 2

    def __init__(
            self,
            destination: Path,
            resource: Resource,
            fresh_install=True,
            initial_state=State.DOWNLOADING
    ):
        self.destination = destination
        self.resource = resource
        self.downloading_destination = self.get_downloading_destination()
        self.lock = asyncio.Lock()
        self.state = initial_state

        if fresh_install:
            assert initial_state == ResourceFile.State.DOWNLOADING

            destination.unlink(missing_ok=True)
            self.downloading_destination.unlink(missing_ok=True)

        self.offsets: list[int] = [0] + list(accumulate(piece.size_bytes for piece in resource.pieces))

    def get_downloading_destination(self) -> Path:
        return self.destination.parent.joinpath(f'.torrentinno-{self.destination.name}')

    def _calculate_offset(self, piece_index: int, piece_inner_offset: int) -> int:
        return self.offsets[piece_index] + piece_inner_offset

    async def _create_downloading_destination(self):
        self.downloading_destination.unlink(missing_ok=True)
        async with aiofiles.open(self.downloading_destination, mode='wb') as f:
            for piece in self.resource.pieces:
                await f.write(bytes([0] * piece.size_bytes))

    async def _ensure_downloading_destination(self):
        async with self.lock:
            if (
                    not self.downloading_destination.exists() or
                    self.downloading_destination.stat().st_size != self.offsets[-1]
            ):
                await self._create_downloading_destination()


    async def get_piece(self, index: int) -> bytes:
        return await self.get_block(index, 0, self.resource.pieces[index].size_bytes)

    async def get_block(self, piece_index: int, piece_inner_offset: int, block_length: int) -> bytes:
        offset = self._calculate_offset(piece_index, piece_inner_offset)
        if offset + block_length > self.offsets[-1]:
            raise RuntimeError("The requested read portion does not fit the file")

        take_from: Path
        if self.state == ResourceFile.State.DOWNLOADED:
            take_from = self.destination
        else:
            await self._ensure_downloading_destination()
            take_from = self.downloading_destination

        async with aiofiles.open(take_from, mode='rb') as f:
            await f.seek(offset)
            return await f.read(block_length)

    async def save_block(self, piece_index: int, piece_inner_offset: int, data: bytes):
        if self.state == ResourceFile.State.DOWNLOADED:
            raise RuntimeError("Cannot perform write operation in DOWNLOADED state")

        offset = self._calculate_offset(piece_index, piece_inner_offset)
        if offset + len(data) > self.offsets[-1]:
            raise RuntimeError("The write portion overflows the file")

        await self._ensure_downloading_destination()

        async with aiofiles.open(self.downloading_destination, mode='r+b') as f:
            await f.seek(offset)
            await f.write(data)

    async def save_validated_piece(self, piece_index: int, data: bytes):
        await self.save_block(piece_index, 0, data)

    async def accept_download(self):
        if self.destination.exists():
            self.destination.unlink()
        await aiofiles.os.rename(self.downloading_destination, self.destination)
        self.state = ResourceFile.State.DOWNLOADED
