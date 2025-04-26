import requests
import time
import asyncio

async def update_peer(server_url,peer) -> str:
    '''
    Using post requests create or update peer information on tracker server
    '''
    try:
        response = requests.post(server_url, json=peer, timeout=5)
        if response.status_code == 200:
            print("Peer updated successfully.")
        else:
            print(f"Failed to update peer. Status code: {response.status_code}")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error updating peer: {e}")
        return ''