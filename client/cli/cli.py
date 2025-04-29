import asyncio
import datetime
import threading
from pathlib import Path
import json

from core.common.resource import Resource


def get_help_message() -> str:
    return (
        'TorrentInno CLI reference:\n\n'

        '"help" - display this message\n'

        '"quit" - quit the CLI and terminate the torrent session\n'

        '"download <destination-file> <resource-file.json>" - '
        'start downloading the file associated with <resource-file.json> into the <destination-file>\n'

        '"share <path-to-file> <resource-file.json>" - '
        'start sharing the existing <path-to-file> with other peers. The <resource-file.json>'
        'is the metadata of the filet\n'

        '"show all" - show the status of all files\n'

        '"show <file-id>" - show the status of file with <file-id>\n'

        '"generate resource <file> <path-to-generated-resource>" - generate the resource json of the <file> '
        'and save the result into <path-to-generated-resource>'
    )


def create_resource_from_file(file: Path):
    with open(file, mode='r') as f:
        resource_dict = json.load(f)
        resource = Resource(
            tracker_ip=resource_dict["trackerIp"],
            tracker_port=resource_dict["trackerPort"],
            comment=resource_dict["comment"],
            creation_date=datetime.datetime.fromisoformat(resource_dict["creationDate"]),
            name=resource_dict["name"],
            pieces=[
                Resource.Piece(
                    sha256=piece_dict['sha256'],
                    size_bytes=int(piece_dict['size'])
                )
                for piece_dict in resource_dict["pieces"]
            ]
        )
        print(resource_dict, resource)
        return resource


class Client:
    async def start(self):
        print(
            "Welcome to TorrentInno CLI\n"
            "Type \"help\" to display the help message\n"
            "To exit type \"quit\""
        )
        try:
            self.infinite_loop()
        except KeyboardInterrupt:
            print("Quitting")

    def infinite_loop(self):
        while True:
            print(">", end=' ')
            line = input()
            if line == "help":
                print(get_help_message())
                continue
            if line == "quit":
                print("Quitting")
                break
            tokens = line.split(' ')
            if tokens[0] == "download":
                try:
                    destination = Path(tokens[1])
                    resource_file = Path(tokens[2])
                    if destination.exists():
                        print(f"The {destination} already exists. Abort download")
                        continue
                    resource = create_resource_from_file(resource_file)
                    # TODO: start the download somehow
                except Exception as e:
                    print(f"Download failed: {e}")
                    continue


def main():
    client = Client()
    asyncio.run(client.start())
