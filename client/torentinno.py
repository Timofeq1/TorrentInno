import asyncio
import random
import json
import requests
import time

from client.core.s2p.server_manager import update_peer
from core.p2p import resource_manager
from core.s2p.server_manager import update_peer
from core.common.peer_info import PeerInfo
from core.common.resource import Resource

def generate_random_bits(size) -> bytes:
    return bytes(random.randint(0, 255) for _ in range(size))

def generate_random_peer_id() -> str:
    return generate_random_bits(32).hex()

def get_peer_public_ip():
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        return response.json()['ip']
    except Exception as e:
        return None

async def share_file(path, resource: Resource): #name can be changed
    peer_id = generate_random_peer_id()
    file_path = path
    resource_manager_instance = resource_manager.ResourceManager(peer_id, file_path, resource, has_file=True)
    port = await resource_manager_instance.open_public_port()
    await resource_manager_instance.start_sharing_file()
    peer_ip =get_peer_public_ip()
    peer_info = PeerInfo(peer_ip, port, peer_id)

    peer_json = {
        "peerId": peer_info.peer_id,
        "infoHash": resource.get_info_hash(),
        "publicIp": peer_info.public_ip,
        "publicPort": peer_info.public_port,
    }

    server_url = f"http://{resource.tracker_ip}:{resource.tracker_port}/peers"

    while True:
        peer_list_str = await update_peer(server_url,peer_json)
        peer_list = json.loads(peer_list_str)
        await resource_manager_instance.submit_peers(peer_list)
        time.sleep(25)
