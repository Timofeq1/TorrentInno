import asyncio
import random
import json
import socket
import datetime
import os
import hashlib
from typing import Dict

from core.p2p.resource_manager import ResourceManager
from core.s2p.server_manager import update_peer
from core.p2p.resource_manager import ResourceManager
from core.s2p.server_manager import heart_beat
from core.common.peer_info import PeerInfo
from core.common.resource import Resource

# --- constants ---
TRACKER_IP = '80.71.232.39'
TRACKER_PORT = '8080'

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


TRACKER_IP = '80.71.232.39'
TRACKER_PORT = '8080'
peer_id = generate_peer_id()
resource_manager_dict: Dict[str, ResourceManager] = {}

def create_resource_json(name: str, comment: str, file_path, piece_size: int = 1024 * 1024):
    '''
    Create a resource by splitting the file into multiple pieces.
    '''
    size_bytes = os.path.getsize(file_path)
    pieces = []

    with open(file_path, 'rb') as f:
        while True:
            file_bytes = f.read(piece_size)
            if not file_bytes:
                break
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            pieces.append({
                'sha256': sha256,
                'size': len(file_bytes)
            })

    resource_json = {
        'trackerIp': TRACKER_IP,
        'trackerPort': TRACKER_PORT,
        'comment': comment,
        'creationDate': datetime.datetime.now().isoformat(),
        'name': name,
        'pieces': pieces
    }

    return resource_json


def create_resource_from_json(resource_json):
    '''
    Create a resource from the given JSON data.
    '''
    pieces = [Resource.Piece(**piece) for piece in resource_json['pieces']]
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

    peer_id = generate_peer_id()
    resource_manager_dict: Dict[str, ResourceManager] = {}

    async def start_share_file(destination, resource: Resource, self):
        '''
        Function what starting sharing of file, and updating peer information
        on tracker server
        '''
        peer_public_ip = get_peer_public_ip()
        local_resource_manager = ResourceManager(self.peer_id, destination, resource)
        self.resource_manager_dict[destination] = local_resource_manager
        peer_public_port = await self.resource_manager_dict.get(destination).full_start()
        resource_info_hash = resource.get_info_hash()
        peer = {
            "peerId": self.peer_id,
            "infoHash": resource_info_hash,
            "publicIp": peer_public_ip,
            "publicPort": peer_public_port
        }
        tracker_url = f'http://{TRACKER_IP}:{TRACKER_PORT}/peers'

        async def parse_peer_list(json_text):
            '''
            Function what parse json text and return list of peerInfo elements
            '''
            peer_list = []


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
                print(f"Error parsing peer list: {e}")

            await self.resource_manager_dict.get(destination).submit_peers(peer_list)

        task = asyncio.create_task((heart_beat(tracker_url, peer, parse_peer_list)))

    async def stop_share_file(destination, self):
        await self.resource_manager_dict.get(destination).stop_sharing_file()
        del self.resource_manager_dict[destination]

    async def start_download_file(destination, resource: Resource, self):
        '''
        Function what starting downloading of file, and updating peer information
        on tracker server
        '''
        peer_public_ip = get_peer_public_ip()
        local_resource_manager = ResourceManager(self.peer_id, destination, resource)
        self.resource_manager_dict[destination] = local_resource_manager
        peer_public_port = await self.resource_manager_dict.get(destination).full_start()
        resource_info_hash = resource.get_info_hash()
        peer = {
            "peerId": self.peer_id,
            "infoHash": resource_info_hash,
            "publicIp": peer_public_ip,
            "publicPort": peer_public_port
        }

        tracker_url = f'http://{TRACKER_IP}:{TRACKER_PORT}/peers'

        async def parse_peer_list(json_text):
            '''
            Function what parse json text and return list of peerInfo elements
            '''
            peer_list = []

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
                print(f"Error parsing peer list: {e}")

            await self.resource_manager_dict.get(destination).submit_peers(peer_list)

        task = asyncio.create_task((heart_beat(tracker_url, peer, parse_peer_list)))
        await self.resource_manager_dict.get(destination).start_download()


    async def stop_download_file(destination, self):
        '''
        Function what stopping downloading of file, and updating peer information
        on tracker server
        '''
        await self.resource_manager_dict.get(destination).stop_download()
        del self.resource_manager_dict[destination]


    async def get_state(destination, self):
        '''
        Function what starting downloading of file, and updating peer information
        on tracker server
        '''

        return await self.resource_manager_dict.get(destination).get_state()

    async def get_all_files_state(self):
        '''
        Function what returning state of all files
        '''
        return_list = []

        for key in self.resource_manager_dict.keys():
            return_list.append(tuple(key, self.resource_manager_dict.get(key).get_state()))

        return return_list
