import asyncio
import hashlib
from pathlib import Path

import random
from core.p2p.connection import Connection
from core.p2p.message import Handshake, Request, Piece, Bitfield
from core.p2p.resource_file import ResourceFile
from core.common.resource import Resource
from core.p2p.connection_listener import ConnectionListener
from enum import Enum
import logging


class ResourceManager(ConnectionListener):
    class PieceStatus(Enum):
        FREE = 1  # The piece is not in work
        IN_PROGRESS = 2  # Waiting for reply from some peer
        RECEIVED = 3  # The data has been fetched from network and now is saving on disk
        SAVED = 4  # Piece is successfully saved on disk

    async def _send_bitfield(self, connection: Connection):
        stored_pieces = list(
            piece_status == ResourceManager.PieceStatus.SAVED for piece_status in self._piece_status
        )
        await connection.send_message(Bitfield(stored_pieces))

    # Some new peer wants to connect to this peer
    async def _handle_incoming_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        host, port = writer.get_extra_info('peername')
        try:
            response = await reader.readexactly(74)
            assert response[0:11].decode() == 'TorrentInno'
            assert response[43:75].hex() == self.info_hash

            peer_id: str = response[11:43].hex()

            # If we already have connection with this peer id -> abort the incoming connection
            if peer_id in self.connections.keys():
                return

            # If everything is correct, then send the response handshake message
            writer.write(Handshake(peer_id=self.host_peer_id, info_hash=self.info_hash).to_bytes())
            await writer.drain()

            # Create the connection object
            connection = Connection(reader, writer, self.resource)
            connection.add_listener(self._create_connection_listener(peer_id))
            self._add_peer(peer_id, connection)

            # Send the message about the stored pieces
            await self._send_bitfield(connection)

            logging.info(f"Establish connection with {peer_id} on port {port}")
        except Exception as e:
            logging.warning(f"Failed to handle incoming connection with {host}")
        finally:
            writer.close()
            await writer.wait_closed()

    def _create_connection_listener(self, peer_id: str) -> ConnectionListener:
        class Listener(ConnectionListener):
            def __init__(self, resource_manager: 'ResourceManager'):
                self.resource_manager = resource_manager

            async def on_request(self, request: Request):
                logging.debug(f"Request message from {peer_id}: {request}")
                try:
                    data = await self.resource_manager.resource_file.get_block(
                        request.piece_index,
                        request.piece_inner_offset,
                        request.block_length
                    )
                    connection = self.resource_manager.connections[peer_id]
                    await connection.send_message(
                        Piece(
                            request.piece_index,
                            request.piece_inner_offset,
                            request.block_length,
                            data
                        )
                    )
                    logging.info(f"Send piece {request.piece_index} on Request message for peer {peer_id}")
                except Exception:
                    logging.exception(f"Exception on request message from peer {peer_id}")
                    pass

            async def on_piece(self, piece: Piece):
                logging.debug(f"Piece message from {peer_id}: {piece}")
                # This peer is not anymore in charge on this piece
                if self.resource_manager._peer_in_charge[piece.piece_index] != peer_id:
                    logging.info(f"Discard piece {piece.piece_index} from {peer_id} as not in charge")
                    return

                self.resource_manager._piece_status[piece.piece_index] = ResourceManager.PieceStatus.RECEIVED
                try:
                    # Check that the received piece matches the hash
                    assert hashlib.sha256(piece.data).hexdigest() == self.resource_manager.resource.pieces[
                        piece.piece_index].sha256

                    await self.resource_manager.resource_file.save_block(
                        piece.piece_index,
                        piece.piece_inner_offset,
                        piece.data
                    )

                    # If the piece is saved, then broadcast the bitfield to all connections and change the status
                    self.resource_manager._piece_status[piece.piece_index] = ResourceManager.PieceStatus.SAVED
                    await asyncio.gather(
                        *(self.resource_manager._send_bitfield(connection)
                          for connection in self.resource_manager.connections.values())
                    )
                    logging.info(f"Save piece {piece.piece_index} from {peer_id}")
                except Exception:
                    logging.exception(f"Exception on piece message from peer {peer_id}")
                    self.resource_manager._piece_status[piece.piece_index] = ResourceManager.PieceStatus.FREE
                    pass

            async def on_bitfield(self, bitfield: Bitfield):
                logging.debug(f"Bitfield message from {peer_id}: {bitfield}")
                self.resource_manager.bitfields[peer_id] = bitfield.bitfield
                logging.info(f"Bitfield from {peer_id}")

            async def on_close(self, cause):
                # The connection with peer for some reason is closed
                logging.info(f"The connection with {peer_id} is closed")
                await self.resource_manager._remove_peer(peer_id)

        return Listener(self)

    def _add_peer(self, peer_id: str, connection: Connection):
        self.connections[peer_id] = connection
        self.bitfields[peer_id] = [False] * len(self.resource.pieces)
        self._free_peers.add(peer_id)

    async def _remove_peer(self, peer_id: str):
        try:
            await self.connections[peer_id].close()
        except Exception as e:
            # Ignore any exception with closing (probably peer_id either is not in list or connection is already closed
            pass
        self.connections.pop(peer_id, None)
        self.bitfields.pop(peer_id, None)
        self._free_peers.remove(peer_id)

    # -----MAIN DOWNLOAD LOGIC BEGINS HERE-----

    async def _download_work(self, peer_id: str, piece_index: int):
        connection = self.connections[peer_id]
        await connection.send_message(
            Request(
                piece_index,
                0,
                self.resource.pieces[piece_index].size_bytes
            )
        )
        await asyncio.sleep(60)  # Sleep 1 minute
        if self._piece_status[piece_index] == ResourceManager.PieceStatus.IN_PROGRESS:
            # If after one minute, the piece is still in progress,
            # then something is wrong with peer (slow download speed or smth)
            self._peer_in_charge[piece_index] = ''  # This peer is no more responsible for this piece
            self._piece_status[piece_index] = ResourceManager.PieceStatus.FREE

    async def _download_loop(self):
        works = set()
        while True:
            # Find free pieces
            free_pieces: list[int] = []
            for i, status in enumerate(self._piece_status):
                if status == ResourceManager.PieceStatus.FREE:
                    free_pieces.append(i)

            # Shuffle the pieces
            random.shuffle(free_pieces)

            # Try to find piece and peer that has this piece
            for piece_index in free_pieces:
                for peer_id in self._free_peers:
                    if self._peer_has_piece(peer_id, piece_index):  # Peer has this piece -> run the work
                        # Update the status and related peer
                        self._piece_status[piece_index] = ResourceManager.PieceStatus.IN_PROGRESS
                        self._peer_in_charge[piece_index] = peer_id

                        task = asyncio.create_task(self._download_work(peer_id, piece_index))
                        task.add_done_callback(works.discard)
                        works.add(asyncio.create_task(self._download_work))

            await asyncio.sleep(0.2)

    # -----END OF DOWNLOAD LOGIC-----

    def _peer_has_piece(self, peer_id: str, piece_index: int) -> bool:
        return self.bitfields[peer_id][piece_index] == True

    async def _run_server_task(self, server: asyncio.Server):
        async with server:
            await server.serve_forever()

    def __init__(
            self,
            host_peer_id: str,
            destination: Path,
            resource: Resource,
            has_file
    ):
        self.host_peer_id = host_peer_id
        self.destination = destination
        self.resource = resource
        self.has_file = has_file

        self.resource_file = ResourceFile(destination, resource, fresh_install=False)
        self.info_hash = resource.get_info_hash()

        # dict peer_id <-> Connection
        self.connections: dict[str, Connection] = dict()

        # dict peer_id <-> pieces (bitfield) this peer has
        self.bitfields: dict[str, list[bool]] = dict()

        if has_file and not destination.exists():
            raise RuntimeError("The caller does not have the file")

        # These fields are needed for download
        self._free_peers: set[str] = set()

        # Fill the initial status of the pieces
        # If the caller passes True to the has_file, then we assume that all pieces are downloaded
        _default_piece_status = ResourceManager.PieceStatus.SAVED if has_file else ResourceManager.PieceStatus.FREE
        self._piece_status: list[ResourceManager.PieceStatus] = \
            [ResourceManager.PieceStatus.SAVED] * len(self.resource.pieces)

        # Current peer that handles this piece
        self._peer_in_charge: list[str] = [''] * len(self.resource.pieces)

        # Various asyncio background tasks
        self._download_task: asyncio.Task | None = None
        self._server_task: asyncio.Task | None = None

    # PUBLIC METHODS:

    async def open_public_port(self) -> int:
        # Start accepting peer connections on some random port
        public_server = await asyncio.start_server(
            lambda r, w: self._handle_incoming_connection(r, w),
            host='0.0.0.0',
            port=0
        )
        host, port = public_server.sockets[0].getsockname()
        self._server_task = asyncio.create_task(self._run_server_task(public_server))
        # Return port on which connection has been opened
        return port

    async def close_public_port(self):
        # Close the server_task connection
        if self._server_task is not None:
            self._server_task.cancel()

    async def start_download(self):
        # Start downloading the resource
        if self._download_task is None:
            self._download_task = asyncio.create_task(self._download_loop())

    async def stop_download(self):
        # Stop downloading the resource
        self._download_task.cancel()
        self._download_task = None
