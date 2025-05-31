import requests
import time
import asyncio
import logging

def update_peer(server_url, peer) -> str:
    logging.info(server_url)
    '''
    Using post requests create or update peer information on tracker server
    '''
    try:
        response = requests.post(server_url, json=peer, timeout=5)
        if response.status_code == 200:
            logging.info("Peer updated successfully.")
        else:
            logging.info(f"Failed to update peer. Status code: {response.status_code}")
            logging.info(f"Response content: {response.text}")  # Log the response content for debugging
        return response.text
    except requests.exceptions.RequestException as e:
        logging.info(f"Error updating peer: {e}")
        return ''

async def heart_beat(server_url, peer, on_tracker_response) -> str:
   while True:
       response_text = update_peer(server_url, peer)
       await on_tracker_response(response_text)
       await asyncio.sleep(30)
