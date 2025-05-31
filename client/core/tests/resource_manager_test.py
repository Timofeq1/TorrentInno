import asyncio
import hashlib
import datetime
from itertools import accumulate
from pathlib import Path
import random
import shutil
import logging
import time
import aiofiles

from core.common.peer_info import PeerInfo
from core.common.resource import Resource
from core.p2p.resource_manager import ResourceManager


def random_bytes(size) -> bytes:
    return bytes(random.randint(0, 255) for _ in range(size))


def random_peer_id() -> str:
    return random_bytes(32).hex()


async def create_peer(peer_id: str, destination: Path, resource) -> tuple[PeerInfo, ResourceManager]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    resource_manager = ResourceManager(peer_id, destination, resource)
    port = await resource_manager.full_start()
    peer_info = PeerInfo('127.0.0.1', port, peer_id)
    return peer_info, resource_manager


def setup_logging():
    log_file = Path(__file__).parent.joinpath("resource_manager_test.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG
    )


async def main():
    setup_logging()

    # Temporary directory and necessary file tree manipulations
    tmp = Path(__file__).parent.joinpath('tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    # Make the randomizer deterministic
    random.seed(0)

    # Generate the initial file
    source_peer_id = random_peer_id()
    source_peer_destination = tmp.joinpath('source', 'data')
    source_peer_destination.parent.mkdir(parents=True)
    piece_sizes = [random.randint(5 * 10 ** 5, 10 ** 6) for _ in range(10)]
    offset = [0] + list(accumulate(piece_sizes))

    with open(source_peer_destination, mode='wb') as file:
        file.seek(offset[-1] - 1)
        file.write(b'\0')

    print("Start generating file...")
    pieces = []
    async with aiofiles.open(source_peer_destination, mode='r+b') as file:
        for i in range(len(piece_sizes)):
            await file.seek(offset[i])
            arr = random_bytes(min(100, piece_sizes[i]))
            data = arr * (piece_sizes[i] // len(arr)) + b'\0' * (piece_sizes[i] % len(arr))
            assert len(data) == piece_sizes[i]
            piece = Resource.Piece(
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data)
            )
            pieces.append(piece)
            await file.write(data)

    assert source_peer_destination.stat().st_size == offset[-1]

    resource = Resource(
        tracker_ip='0.0.0.0',
        tracker_port=8080,
        comment='Test file',
        creation_date=datetime.datetime(year=2000, month=1, day=1, hour=1, minute=1, second=1),
        name='Random testing file',
        pieces=pieces
    )

    source_peer_info, source_resource_manager = await create_peer(
        source_peer_id,
        source_peer_destination,
        resource
    )

    # Now create consumer peers
    consumer_peer_ids = [random_peer_id() for _ in range(5)]
    consumer_destinations = [
        tmp.joinpath(consumer_peer_id, resource.name)
        for consumer_peer_id in consumer_peer_ids
    ]
    consumer_tuples = [
        await create_peer(
            consumer_peer_id,
            consumer_destination,
            resource
        ) for consumer_peer_id, consumer_destination in zip(consumer_peer_ids, consumer_destinations)
    ]
    consumer_peer_infos = [t[0] for t in consumer_tuples]
    consumer_resource_managers = [t[1] for t in consumer_tuples]

    all_peer_infos = [source_peer_info] + consumer_peer_infos

    # Submit the info about peers to all peers
    await asyncio.gather(
        source_resource_manager.submit_peers(all_peer_infos),
        *(
            consumer_resource_manager.submit_peers(all_peer_infos)
            for consumer_resource_manager in consumer_resource_managers
        )
    )


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(main())
        loop.run_forever()
    finally:
        pass
        tmp = Path(__file__).parent.joinpath('tmp')
        shutil.rmtree(tmp)
