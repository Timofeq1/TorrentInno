import aiofiles
import pytest
import random
import asyncio
from pathlib import Path
from core.p2p.resource_file import ResourceFile
from core.tests.mocks import mock_resource


@pytest.mark.asyncio
async def test_resource_file(tmp_path):
    data: list[bytes] = []
    for piece in mock_resource.pieces:
        data.append(bytes(random.randint(0, 255) for _ in range(piece.size_bytes)))

    destination = tmp_path / 'test_file'

    resource_file = ResourceFile(destination, mock_resource)

    async def write_piece(piece_index: int, piece_data: bytes):
        await resource_file.save_validated_piece(piece_index, piece_data)

    # Write all the pieces concurrently
    await asyncio.gather(
        *(write_piece(i, piece_data) for i, piece_data in enumerate(data))
    )

    # Accept the download (simulate renaming)
    await resource_file.accept_download()

    # Ensure the file content is correctly saved and pieces are correctly fetched by resource_file
    async with aiofiles.open(destination, mode='rb') as f:
        for piece_index, piece_data in enumerate(data):
            on_file = await f.read(len(piece_data))
            from_resource_file = await resource_file.get_piece(piece_index)
            assert on_file == piece_data
            assert piece_data == from_resource_file

    # Ensure the downloading resource is moved and no longer exists
    assert not resource_file.get_downloading_destination().exists()
