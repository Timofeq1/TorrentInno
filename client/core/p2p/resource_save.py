from pathlib import Path
import json

import aiofiles

from core.common.resource import Resource


class ResourceSave:
    def __init__(self, destination: Path, resource: Resource):
        self.save_file = \
            destination.parent.joinpath(f".torrentinno_save-file_{destination.name}_{resource.get_info_hash()}")

    async def remove_save(self):
        self.save_file.unlink(missing_ok=True)

    async def read_bitfield(self) -> list[bool]:
        async with aiofiles.open(self.save_file, mode='r') as f:
            result = json.loads(await f.read())
            return result

    async def write_bitfield(self, bitfield: list[bool]):
        async with aiofiles.open(self.save_file, mode='w') as f:
            await f.write(json.dumps(bitfield))
