import requests
import time
import asyncio

SERVER_URL = "http://localhost:8080/peers"  # * Replace with server URL

async def update_peer(peer):
    '''
    Using post requests create or update peer information on tracker server
    '''
    try:
        responce = requests.post(SERVER_URL, json=peer, timeout=5)
        if responce.status_code == 200:
            print("Peer updated successfully.")
        else:
            print(f"Failed to update peer. Status code: {responce.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error updating peer: {e}")

async def heart_beat(peer, interval=30):
    '''
    Using update_peer function send peer information to  tracker server to show
    what peer also in live status
    '''
    while True:
        while True:
            update_peer(peer)
            time.sleep(interval)

# peer = {
#     "peerId": "peer123",
#     "infoHash": "hash456",
#     "publicIp": "127.0.0.1",
#     "publicPort": "6881"
# }

# update_peer(peer)