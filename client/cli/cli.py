import asyncio
import logging
import sys
import time
from pathlib import Path
import json
import shlex
import threading
import os

import torrentInno
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
        'is the metadata of the file\n'

        '"show all" - show the status of all files\n'

        '"show <path>" - show the status of file at the path <path>\n'

        '"generate resource <file> <path-to-generated-resource>" - generate the resource json of the <file> '
        'and save the result into <path-to-generated-resource>'
    )


def create_resource_from_file(file: Path) -> Resource:
    with open(file, mode='r') as f:
        resource_json = json.load(f)
        return create_resource_from_json(resource_json)


def _run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def setup_logging():
    log_file = Path(__file__).parent.joinpath('cli_logs.log')
    logging.basicConfig(
        level=logging.DEBUG,
        filename=log_file,
        force=True
    )


class Client:
    def __init__(self):
        setup_logging()
        self.torrent_inno: TorrentInno = TorrentInno()
        self.loop = asyncio.new_event_loop()
        self.background_thread = threading.Thread(target=_run_event_loop, args=(self.loop,))
        self.background_thread.start()

    def start(self):
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

            tokens = shlex.split(line)

            if tokens[0] == "download":
                try:
                    destination = Path(tokens[1]).expanduser()
                    resource_file = Path(tokens[2]).expanduser()
                    if destination.exists():
                        print(f"The {destination} already exists. Abort download")
                        continue
                    resource = create_resource_from_file(resource_file)
                    asyncio.run_coroutine_threadsafe(
                        self.torrent_inno.start_download_file(destination.resolve(), resource),
                        self.loop
                    )
                    print(f"Start downloading a file into {destination.resolve()}")
                except Exception as e:
                    print(f"Download failed: {e}")

            elif len(tokens) == 2 and tokens[0] == "show" and tokens[1] == "all":
                try:
                    states: list[TorrentInno.State] = asyncio.run_coroutine_threadsafe(
                        self.torrent_inno.get_all_files_state(),
                        self.loop
                    ).result()

                    for key, state in states:
                        all_pieces = len(state.piece_status)
                        saved_pieces = sum(state.piece_status)
                        print(
                            f'Destination: {state.destination}\n'
                            f'Upload speed {state.upload_speed_bytes_per_sec / 10 ** 6:.2f} mb/sec\n'
                            f'Download speed {state.download_speed_bytes_per_sec / 10 ** 6:.2f} mb/sec\n'
                            f'Downloaded {saved_pieces}/{all_pieces} pieces\n'
                        )
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
                    asyncio.run_coroutine_threadsafe(
                        self.torrent_inno.start_share_file(destination.resolve(), resource),
                        self.loop
                    )
                    print(f"Start sharing file at {destination}")
                except Exception as e:
                    print(f"Share failed: {e}")

            elif tokens[0] == "show":
                try:
                    destination = Path(tokens[1]).expanduser()

                    while True:
                        # Get the state asynchronously
                        state: TorrentInno.State = asyncio.run_coroutine_threadsafe(
                            self.torrent_inno.get_state(destination.resolve()),
                            self.loop
                        ).result()

                        # Convert speed to MB (1 MB = 10^6 bytes)
                        upload_speed_mb = state.upload_speed_bytes_per_sec / 10 ** 6
                        download_speed_mb = state.download_speed_bytes_per_sec / 10 ** 6

                        # Create the saved_chunks string
                        saved_pieces = ''.join('#' if piece else '.' for piece in state.piece_status)

                        # Clear the terminal
                        os.system('cls' if os.name == 'nt' else 'clear')

                        print(
                            f"Destination: {state.destination}" + " " * 20
                        )  # Add padding to clear longer previous lines
                        print(
                            f"Upload speed: {upload_speed_mb:.2f} mb/sec" + " " * 20
                        )
                        print(
                            f"Download speed: {download_speed_mb:.2f} mb/sec" + " " * 20
                        )
                        print(
                            f"Saved pieces: {saved_pieces}" + " " * 20
                        )

                        # Wait before updating again
                        time.sleep(0.5)
                except KeyboardInterrupt as e:
                    pass # Ignore keyboard interrupt and simply continue
                except Exception as e:
                    print(f"Fail when fetching the status of file: {e}")

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

                    resource_json = create_resource_json(
                        name=name,
                        comment=comment,
                        file_path=file,
                        min_piece_size=64 * 1000,
                        max_pieces=1000
                    )
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
        client.start()
    except Exception as e:
        print("Quitting")
