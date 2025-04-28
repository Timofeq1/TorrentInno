import asyncio
import datetime
import hashlib
from pathlib import Path
import random
import shutil
import logging

from core.common.peer_info import PeerInfo
from core.common.resource import Resource
from core.p2p.resource_manager import ResourceManager


def random_bits(size) -> bytes:
    return bytes(random.randint(0, 255) for _ in range(size))


def random_peer_id() -> str:
    return random_bits(32).hex()


async def main():
    logging.basicConfig(level=logging.DEBUG)

    # Temporary directory
    tmp = Path(__file__).parent.joinpath('tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    # Generate stub data
    data: list[bytes] = [random_bits(random.randint(100, 1000)) for _ in range(10)]
    pieces: list[Resource.Piece] = [
        Resource.Piece(
            sha256=hashlib.sha256(piece_data).hexdigest(),
            size_bytes=len(piece_data)
        )
        for piece_data in data
    ]
    resource = Resource(
        tracker_ip='0.0.0.0',
        tracker_port=8080,
        comment='Test file',
        creation_date=datetime.datetime.now(),
        name='Random testing file',
        pieces=pieces
    )

    # Write the stub data to file
    source_file = tmp.joinpath(resource.name)
    with open(source_file, mode='wb') as f:
        for piece_data in data:
            f.write(piece_data)

    # Set up source peer_id. This can be used as an example of working with ResourceManager
    source_peer_id = random_peer_id() # peer_id is unique PER PEER (not per ResourceManager)
    source_destination = source_file
    source_resource_manager = ResourceManager(source_peer_id, source_destination, resource)
    source_port = await source_resource_manager.open_public_port()
    await source_resource_manager.start_sharing_file()
    source_peer_info = PeerInfo('127.0.0.1', source_port, source_peer_id)

    consumer_peer_ids = [random_peer_id() for _ in range(5)]
    consumer_destinations = [tmp.joinpath(peer_id, resource.name) for peer_id in consumer_peer_ids]
    for consumer_destination in consumer_destinations:
        consumer_destination.parent.mkdir(parents=True)

    consumer_resource_managers = [
        ResourceManager(consumer_peer_id, consumer_destination, resource)
        for consumer_peer_id, consumer_destination in zip(consumer_peer_ids, consumer_destinations)
    ]
    for consumer_resource_manager in consumer_resource_managers:
        await consumer_resource_manager.start_sharing_file()
    consumer_ports = [
        await resource_manager.open_public_port()
        for resource_manager in consumer_resource_managers
    ]
    consumer_peer_infos = [
        PeerInfo('127.0.0.1', port, peer_id)
        for port, peer_id in zip(consumer_ports, consumer_peer_ids)
    ]

    all_peer_infos = consumer_peer_infos + [source_peer_info]

    for resource_manager in consumer_resource_managers:
        await resource_manager.start_download()

    # For all the peers, submit the PeerInfo list
    await asyncio.gather(
        source_resource_manager.submit_peers(all_peer_infos),
        *(
            consumer_resource_manager.submit_peers(all_peer_infos)
            for consumer_resource_manager in consumer_resource_managers
        )
    )

    # ...watch the peers talking!

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

