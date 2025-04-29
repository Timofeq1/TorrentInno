import requests
import time
import asyncio

def update_peer(server_url, peer) -> str:
    print(server_url)
    '''
    Using post requests create or update peer information on tracker server
    '''
    try:
        response = requests.post(server_url, json=peer, timeout=5)
        if response.status_code == 200:
            print("Peer updated successfully.")
        else:
            print(f"Failed to update peer. Status code: {response.status_code}")
            print(f"Response content: {response.text}")  # Log the response content for debugging
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error updating peer: {e}")
        return ''

async def heart_beat(server_url, peer, on_tracker_response) -> str:
   while True:
       response_text = update_peer(server_url, peer)
       await on_tracker_response(response_text)
       await asyncio.sleep(30)
