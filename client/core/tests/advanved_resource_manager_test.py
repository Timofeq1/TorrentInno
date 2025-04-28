import asyncio
import datetime
import hashlib
from pathlib import Path
import random
import json
import shutil
import logging

from core.common.peer_info import PeerInfo
from core.common.resource import Resource
from core.p2p.resource_file import ResourceFile
from core.p2p.resource_manager import ResourceManager
from core.p2p.resource_save import ResourceSave

random.seed(0)


def random_bits(size) -> bytes:
    return bytes(random.randint(0, 255) for _ in range(size))


def random_peer_id() -> str:
    return random_bits(32).hex()


async def simulate_ownership(bitfield: list[bool], data: list[bytes], destination: Path, resource: Resource):
    resource_file = ResourceFile(destination, resource)
    resource_save = ResourceSave(destination, resource)
    await resource_save.write_bitfield(bitfield)
    for i, piece_status in enumerate(bitfield):
        if piece_status:
            await resource_file.save_validated_piece(i, data[i])


test_run = 1


async def main():
    logging.basicConfig(level=logging.DEBUG)

    # Temporary directory
    tmp = Path(__file__).parent.joinpath('tmp')
    # shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

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
        creation_date=datetime.datetime(year=2000, month=1, day=1, hour=1, minute=1, second=1),
        name='Random testing file',
        pieces=pieces
    )

    source_peer_id = random_peer_id()  # peer_id is unique PER PEER (not per ResourceManager)
    source_destination = tmp.joinpath('source', resource.name)
    source_destination.parent.mkdir(parents=True, exist_ok=True)

    # Example where the initial peer has only some parts
    source_bitfield = [False] * len(resource.pieces)
    source_bitfield[0] = True
    source_bitfield[1] = True
    source_bitfield[-1] = True
    await simulate_ownership(source_bitfield, data, source_destination, resource)

    # Set up source peer_id. This can be used as an example of working with ResourceManager
    source_resource_manager = ResourceManager(source_peer_id, source_destination, resource)
    source_port = await source_resource_manager.full_start()
    source_peer_info = PeerInfo('127.0.0.1', source_port, source_peer_id)

    consumer_peer_ids = [random_peer_id() for _ in range(5)]
    consumer_destinations = [tmp.joinpath(peer_id, resource.name) for peer_id in consumer_peer_ids]
    for consumer_destination in consumer_destinations:
        consumer_destination.parent.mkdir(parents=True, exist_ok=True)

    # For first consumer simulate ownership of some other parts
    consumer_0_bitfield = [False] * len(resource.pieces)
    consumer_0_bitfield[1] = True
    consumer_0_bitfield[2] = True
    consumer_0_bitfield[3] = True
    consumer_0_bitfield[-2] = True
    await simulate_ownership(consumer_0_bitfield, data, consumer_destinations[0], resource)

    consumer_resource_managers = [
        ResourceManager(consumer_peer_id, consumer_destination, resource)
        for consumer_peer_id, consumer_destination in zip(consumer_peer_ids, consumer_destinations)
    ]
    consumer_ports = [
        await resource_manager.full_start()
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

    await asyncio.sleep(5)

    print("Source peer disconnected!")
    await source_resource_manager.shutdown()  # Sudden shutdown of source resource manager

    await asyncio.sleep(2)
    print("Adding new sudden peer")

    sudden_peer_id = random_peer_id()
    sudden_peer_destination = tmp.joinpath(sudden_peer_id, resource.name)
    sudden_peer_destination.parent.mkdir(parents=True)
    sudden_peer_bitfield = [False] * 10
    sudden_peer_bitfield[3:-2] = [True] * len(sudden_peer_bitfield[3:-2])
    await simulate_ownership(sudden_peer_bitfield, data, sudden_peer_destination, resource)
    sudden_peer_resource_manager = ResourceManager(sudden_peer_id, sudden_peer_destination, resource)
    sudden_peer_port = await sudden_peer_resource_manager.full_start()
    sudden_peer_info = PeerInfo('127.0.0.1', sudden_peer_port, sudden_peer_id)

    all_peer_infos = all_peer_infos + [sudden_peer_info]

    # For all the peers, submit the PeerInfo (yes, again)
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
        print("\nSTOPPING LOOP\n")
        loop.stop()
        print("\nSTARTING AGAIN, NOW WITH SAVED DATA\n")
        loop.create_task(main())
    finally:
        pass
        tmp = Path(__file__).parent.joinpath('tmp')
        shutil.rmtree(tmp)
