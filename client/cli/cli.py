import asyncio
from pathlib import Path
import json
import shlex

from core.common.resource import Resource
from torrentInno import TorrentInno, create_resource_json, create_resource_from_json


def get_help_message() -> str:
    return (
        'TorrentInno CLI reference:\n\n'

        '"help" - display this message\n'

        '"quit" - quit the CLI and terminate the torrent session\n'

        '"download <destination-file> <resource-file.json>" - '
        'start downloading the file associated with <resource-file.json> into the <destination-file>\n'

        '"share <path-to-file> <resource-file.json>" - '
        'start sharing the existing <path-to-file> with other peers. The <resource-file.json> '
        'is the metadata of the filet\n'

        '"show all" - show the status of all files\n'

        '"show <path>" - show the status of file at the path <path>\n'

        '"generate resource <file> <path-to-generated-resource>" - generate the resource json of the <file> '
        'and save the result into <path-to-generated-resource>'
    )


def create_resource_from_file(file: Path) -> Resource:
    with open(file, mode='r') as f:
        resource_json = json.load(f)
        return create_resource_from_json(resource_json)


class Client:
    def __init__(self):
        self.torrent_inno: TorrentInno = None  # TODO: initialize in start()

    async def start(self):
        print(
            "Welcome to TorrentInno CLI\n"
            "Type \"help\" to display the help message\n"
            "To exit type \"quit\""
        )
        try:
            await self.infinite_loop()
        except KeyboardInterrupt:
            print("Quitting")

    async def infinite_loop(self):
        while True:
            print(">", end=' ')
            line = input()
            if line == "help":
                print(get_help_message())
                continue

            if line == "quit":
                print("Quitting")
                break

            tokens = shlex.split(line)

            if tokens[0] == "download":
                try:
                    destination = Path(tokens[1]).expanduser()
                    resource_file = Path(tokens[2]).expanduser()
                    if destination.exists():
                        print(f"The {destination} already exists. Abort download")
                        continue
                    resource = create_resource_from_file(resource_file)
                    await self.torrent_inno.start_download_file(destination.resolve(), resource)
                    print(f"Start downloading a file into {destination.resolve()}")
                except Exception as e:
                    print(f"Download failed: {e}")

            elif len(tokens) == 2 and tokens[0] == "show" and tokens[1] == "all":
                try:
                    states = await self.torrent_inno.get_all_files_state()
                    for state in states:
                        print(state)
                except Exception as e:
                    print(f"Something went wrong: {e}")

            elif tokens[0] == "share":
                try:
                    destination = Path(tokens[1]).expanduser()
                    resource_file = Path(tokens[2]).expanduser()
                    if not destination.exists():
                        print(f"The {destination} does not exist. Abort share")
                        continue
                    resource = create_resource_from_file(resource_file)
                    await self.torrent_inno.start_share_file(destination.resolve(), resource)
                    print(f"Start sharing file at {destination}")
                except Exception as e:
                    print(f"Share failed: {e}")

            elif tokens[0] == "show":
                try:
                    destination = Path(tokens[1]).expanduser()
                    state = await self.torrent_inno.get_state(destination.resolve())
                    print(state)
                except Exception as e:
                    print(f"Fail when fetching the status of file at {tokens[0]}: {e}")

            elif len(tokens) == 4 and tokens[0] == "generate" and tokens[1] == "resource":
                try:
                    file = Path(tokens[2]).expanduser()
                    resource_file = Path(tokens[3]).expanduser()

                    print(file.resolve())

                    if not file.exists():
                        print(f"File {file.resolve()} does not exist. Abort generation")
                        continue

                    # Start the interactive session
                    print("Enter the comment: ")
                    comment = input()

                    print("Enter the name of the resource file: ")
                    name = input()

                    resource_json = create_resource_json(name=name, comment=comment, file_path=file)
                    with open(resource_file, mode='w') as f:
                        json.dump(resource_json, f, indent=4, ensure_ascii=False)
                    print("Successfully created")
                except Exception as e:
                    print(f"Failed when generating the resource file: {e}")
            else:
                print("Unknown command")


def main():
    try:
        client = Client()
        asyncio.run(client.start())
    except Exception as e:
        print("Quitting")
