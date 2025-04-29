import asyncio
from torrentInno import TorrentInno, create_resource_json, create_resource_from_json
from core.common.resource import Resource
import logging

logging.basicConfig(level=logging.DEBUG)

async def main():
    client1 = TorrentInno()
    print(client1.peer_id)
    client2 = TorrentInno()
    print(client2.peer_id)

    resource_json = create_resource_json('Lab_8_Docker.html', 'presentation for 5', '/home/setterwars/Downloads/Lab_8_Docker.html')
    resource: Resource = create_resource_from_json(resource_json)

    await client1.start_share_file('/home/setterwars/Downloads/Lab_8_Docker.html', resource)
    await asyncio.sleep(2)
    await client2.start_download_file('/home/setterwars/Documents/Lab_8_Docker.html', resource)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(main())
    loop.run_forever()