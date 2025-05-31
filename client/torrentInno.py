import asyncio
import random
import json
import socket
import datetime
import os
import hashlib
import math
import logging

from typing import Dict
from pathlib import Path
from dataclasses import dataclass

from core.p2p.resource_manager import ResourceManager
from core.s2p.server_manager import update_peer, heart_beat
from core.common.peer_info import PeerInfo
from core.common.resource import Resource

# --- constants ---
TRACKER_IP = '80.71.232.39'
TRACKER_PORT = 8080

logging.basicConfig(level=logging.INFO)

# --- utility functions ---

def generate_random_bits(size) -> bytes:
    '''
    Generate random bits using randint
    '''
    return bytes(random.randint(0, 255) for _ in range(size))

def generate_peer_id() -> str:
    '''
    function what generate peerid
    '''
    return generate_random_bits(32).hex()

def get_peer_public_ip():
    '''
    using request return public ip of the peer
    '''
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    return ip

def create_resource_json(name: str, comment: str, file_path, max_pieces: int = 1000, min_piece_size: int = 64 * 1024):
    '''
    Create a resource by splitting the file into an adaptive number of pieces.
    '''
    size_bytes = os.path.getsize(file_path)
    # Calculate adaptive piece size
    piece_size = max(min_piece_size, math.ceil(size_bytes / max_pieces))
    pieces = []
    total_read = 0

    with open(file_path, 'rb') as f:
        while total_read < size_bytes:
            file_bytes = f.read(piece_size)
            if not file_bytes:
                break
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            pieces.append({
                'sha256': sha256,
                'size': len(file_bytes)
            })
            total_read += len(file_bytes)

    assert total_read == size_bytes, f"Read {total_read} bytes, expected {size_bytes}"
    assert sum(p['size'] for p in pieces) == size_bytes, "Piece sizes do not sum to file size"

    resource_json = {
        'trackerIp': TRACKER_IP,
        'trackerPort': TRACKER_PORT,
        'comment': comment,
        'creationDate': datetime.datetime.now().isoformat(),
        'name': name,
        'pieces': pieces
    }

    logging.info(f"Adaptive split: {len(pieces)} pieces, piece size: {piece_size} bytes")
    return resource_json


def create_resource_from_json(resource_json):
    '''
    Create a resource from the given JSON data.
    '''
    pieces = [Resource.Piece(sha256=piece['sha256'], size_bytes=piece['size']) for piece in resource_json['pieces']]
    resource = Resource(
        tracker_ip=resource_json['trackerIp'],
        tracker_port=resource_json['trackerPort'],
        comment=resource_json['comment'],
        creation_date=datetime.datetime.fromisoformat(resource_json['creationDate']),
        name=resource_json['name'],
        pieces=pieces
    )
    return resource

# --- Torrent logic ---
class TorrentInno:
    @dataclass
    class State:
        piece_status: list[bool]
        upload_speed_bytes_per_sec: int
        download_speed_bytes_per_sec: int
        destination: str

    def __init__(self):
        self.peer_id = generate_peer_id()
        self.resource_manager_dict: Dict[str, ResourceManager] = {}

    async def start_share_file(self, destination: str, resource: Resource):
        '''
        Function what starting sharing of file, and updating peer information
        on tracker server
        '''
        peer_public_ip = get_peer_public_ip()
        local_resource_manager = ResourceManager(self.peer_id, Path(destination), resource)
        self.resource_manager_dict[destination] = local_resource_manager
        peer_public_port = await self.resource_manager_dict.get(destination).full_start()
        resource_info_hash = resource.get_info_hash()
        peer = {
            "peerId": str(self.peer_id),
            "infoHash": str(resource_info_hash),
            "publicIp": str(peer_public_ip),
            "publicPort": str(peer_public_port)
        }
        tracker_url = 'http://' + TRACKER_IP + f':{TRACKER_PORT}/peers'

        async def parse_peer_list(json_text):
            '''
            Function to parse JSON text and return a list of PeerInfo elements.
            '''
            peer_list = []

            if not json_text.strip():
                logging.info("Error parsing peer list: Response is empty")
                return

            try:
                data = json.loads(json_text)
                resource_info_hash = resource.get_info_hash()
                for peer in data.get("peers", []):
                    if peer.get("infoHash") == resource_info_hash:
                        peer_info = PeerInfo(
                            public_ip=peer["publicIp"],
                            public_port=int(peer["publicPort"]),
                            peer_id=peer["peerId"]
                        )
                        peer_list.append(peer_info)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logging.info(f"Error parsing peer list: {e}")
            logging.info("Share peer list:")
            logging.info(peer_list)
            await self.resource_manager_dict.get(destination).submit_peers(peer_list)

        task = asyncio.create_task(heart_beat(tracker_url, peer, parse_peer_list))

    async def stop_share_file(self, destination: str):
        '''
        Function what stopping sharing of file, and updating peer information
        '''
        await self.resource_manager_dict.get(destination).stop_sharing_file()
        await self.resource_manager_dict.get(destination).shutdown()
        del self.resource_manager_dict[destination]


    async def start_download_file(self, destination: str, resource: Resource):
        '''
        Function what starting downloading of file, and updating peer information
        '''
        peer_public_ip = get_peer_public_ip()
        local_resource_manager = ResourceManager(self.peer_id, Path(destination), resource)
        self.resource_manager_dict[destination] = local_resource_manager
        peer_public_port = await self.resource_manager_dict.get(destination).full_start()
        resource_info_hash = resource.get_info_hash()
        peer = {
            "peerId": str(self.peer_id),
            "infoHash": str(resource_info_hash),
            "publicIp": str(peer_public_ip),
            "publicPort": str(peer_public_port)
        }

        tracker_url = 'http://' + TRACKER_IP + f':{TRACKER_PORT}/peers'

        async def parse_peer_list(json_text):
            peer_list = []
            if not json_text.strip():
                logging.info("Error parsing peer list: Response is empty")
                return

            try:
                data = json.loads(json_text)
                resource_info_hash = resource.get_info_hash()
                for peer in data.get("peers", []):
                    if peer.get("infoHash") == resource_info_hash:
                        peer_info = PeerInfo(
                            public_ip=peer["publicIp"],
                            public_port=int(peer["publicPort"]),
                            peer_id=peer["peerId"]
                        )
                        peer_list.append(peer_info)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logging.info(f"Error parsing peer list: {e}")

            filtered_peers = [p for p in peer_list if p.peer_id != self.peer_id]
            await self.resource_manager_dict.get(destination).submit_peers(filtered_peers)
            logging.info('download peer list:')
            logging.info(filtered_peers)

        task = asyncio.create_task(heart_beat(tracker_url, peer, parse_peer_list))
        await self.resource_manager_dict.get(destination).start_download()

    async def stop_download_file(self, destination: str):
        '''
        Function what stopping downloading of file, and updating peer information
        on tracker server
        '''
        await self.resource_manager_dict.get(destination).stop_download()
        await self.resource_manager_dict.get(destination).shutdown()
        del self.resource_manager_dict[destination]

    async def get_state(self, destination):
        '''
        Function what starting downloading of file, and updating peer information
        on tracker server
        '''
        states: ResourceManager.State  = await self.resource_manager_dict.get(destination).get_state()

        return self.State(states.piece_status,
                          states.upload_speed_bytes_per_sec,
                          states.download_speed_bytes_per_sec,
                          destination)

    async def get_all_files_state(self):
        '''
        Function what returning state of all files
        '''
        return_list = []

        for key in self.resource_manager_dict.keys():
            state = await self.resource_manager_dict.get(key).get_state()
            return_list.append((key, self.State(
                state.piece_status,
                state.upload_speed_bytes_per_sec,
                state.download_speed_bytes_per_sec,
                key
            )))

        return return_list

    async def remove_from_torrent(self , destination):
        '''
        Function what removing file from torrent
        '''
        await self.resource_manager_dict.get(destination).shutdown()
        del self.resource_manager_dict[destination]