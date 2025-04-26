import asyncio
import hashlib
from pathlib import Path

import random

from core.common.peer_info import PeerInfo
from core.p2p.connection import Connection, establish_connection
from core.p2p.message import Handshake, Request, Piece, Bitfield
from core.p2p.resource_file import ResourceFile
from core.common.resource import Resource
from core.p2p.connection_listener import ConnectionListener
from enum import Enum
import logging


class ResourceManager:
    class PieceStatus(Enum):
        FREE = 1  # The piece is not in work
        IN_PROGRESS = 2  # Waiting for reply from some peer
        RECEIVED = 3  # The data has been fetched from network and now is saving on disk
        SAVED = 4  # Piece is successfully saved on disk

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

        self.info_hash = resource.get_info_hash()

        # If the peer can give file pieces
        self.share_file = False

        # Peer dictionaries
        self.connections: dict[str, Connection] = dict() # peer_id <-> Connection
        self.bitfields: dict[str, list[bool]] = dict() # peer_id <-> bitfield (owned chunks)
        self._free_peers: set[str] = set() # set of peer ids that are not involved in any work

        self.piece_status: list[ResourceManager.PieceStatus] = []
        if has_file: # The caller claims to already have the file
            self.resource_file = ResourceFile(
                destination,
                resource,
                fresh_install=False,
                initial_state=ResourceFile.State.DOWNLOADED
            )
            self.piece_status = [ResourceManager.PieceStatus.SAVED] * len(self.resource.pieces)
        else: # The caller does not the complete downloaded file
            self.resource_file = ResourceFile(
                destination,
                resource,
                fresh_install=True, # TODO: add normal restoring procedure (for now simply delete any previous files)
                initial_state=ResourceFile.State.DOWNLOADING
            )
            self.piece_status = [ResourceManager.PieceStatus.FREE] * len(self.resource.pieces)

        # Current peer id that handles the piece (empty string=no peer)
        self._peer_in_charge: list[str] = [''] * len(self.resource.pieces)

        # Various asyncio background tasks
        self._download_task: asyncio.Task | None = None
        self._server_task: asyncio.Task | None = None

    def _log(self, msg: str):
        return f"[ResourceManager peer_id={self.host_peer_id[:6]} info_hash={self.info_hash[:6]}] {msg}"

    async def _send_bitfield(self, connection: Connection):
        stored_pieces = list(
            piece_status == ResourceManager.PieceStatus.SAVED for piece_status in self.piece_status
        )
        await connection.send_message(Bitfield(stored_pieces))

    # Some new peer wants to connect to this peer
    async def _handle_incoming_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        host, port = writer.get_extra_info('peername')
        logging.info(self._log(f"{host}:{port} is trying to connect"))
        try:
            response = await reader.readexactly(75)
            assert response[0:11].decode() == 'TorrentInno'
            info_hash = response[43:75].hex()
            assert info_hash == self.info_hash

            peer_id: str = response[11:43].hex()

            if self.host_peer_id < peer_id:
                raise RuntimeError(f"Peer {peer_id} has greater id and is trying to establish connection")

            # If we already have connection with this peer id -> abort the incoming connection
            if peer_id in self.connections:
                return

            # If everything is correct, then send the response handshake message
            writer.write(Handshake(peer_id=self.host_peer_id, info_hash=self.info_hash).to_bytes())
            await writer.drain()

            # Create the connection object
            connection = Connection(reader, writer, self.resource)
            await self._add_peer(peer_id, connection)

            logging.info(self._log(f"Establish connection with {peer_id[:6]}"))
        except Exception as e:
            logging.exception(self._log(f"Failed to handle incoming connection with {host}"))
            writer.close()
            await writer.wait_closed()

    def _create_connection_listener(self, peer_id: str) -> ConnectionListener:
        class Listener(ConnectionListener):
            def __init__(self, resource_manager: 'ResourceManager'):
                self.resource_manager = resource_manager

            async def on_request(self, request: Request):
                if not self.resource_manager.share_file:
                    logging.info(self.resource_manager._log(f"Ignore Request message from peer {peer_id[:6]}"))
                    return

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
                    logging.info(self.resource_manager._log(
                        f"Send piece {request.piece_index} on Request message to peer {peer_id[:6]}"))
                except Exception:
                    logging.exception(self.resource_manager._log(f"Exception on request message from peer {peer_id[:6]}"))
                    pass

            async def on_piece(self, piece: Piece):
                # This peer is not in charge on this piece
                if self.resource_manager._peer_in_charge[piece.piece_index] != peer_id:
                    logging.info(
                        self.resource_manager._log(
                            f"Discard piece {piece.piece_index} from {peer_id[:6]} as not in charge"
                        )
                    )
                    return

                self.resource_manager.piece_status[piece.piece_index] = ResourceManager.PieceStatus.RECEIVED
                try:
                    # Check that the received piece matches the hash
                    assert (
                            hashlib.sha256(piece.data).hexdigest() ==
                            self.resource_manager.resource.pieces[piece.piece_index].sha256
                    )

                    await self.resource_manager.resource_file.save_block(
                        piece.piece_index,
                        piece.piece_inner_offset,
                        piece.data
                    )

                    # If the piece is saved, then broadcast the bitfield to all connections and change the status
                    self.resource_manager.piece_status[piece.piece_index] = ResourceManager.PieceStatus.SAVED

                    saved_pieces = sum(
                        piece_status == ResourceManager.PieceStatus.SAVED
                        for piece_status in self.resource_manager.piece_status
                    )
                    logging.info(self.resource_manager._log(f"Save piece {piece.piece_index} from {peer_id[:6]}"))

                    if saved_pieces == len(self.resource_manager.resource.pieces):
                        # The file is successfully downloaded!
                        await self.resource_manager._confirm_download_complete()

                    await asyncio.gather(
                        *(self.resource_manager._send_bitfield(connection)
                          for connection in self.resource_manager.connections.values()),
                        return_exceptions=True
                    )
                except Exception:
                    logging.exception(self.resource_manager._log(f"Exception on piece message from peer {peer_id[:6]}"))
                    self.resource_manager.piece_status[piece.piece_index] = ResourceManager.PieceStatus.FREE
                    pass

            async def on_bitfield(self, bitfield: Bitfield):
                self.resource_manager.bitfields[peer_id] = bitfield.bitfield
                logging.info(self.resource_manager._log(f"Bitfield from {peer_id[:6]}: {bitfield.bitfield}"))

            async def on_close(self, cause):
                # The connection with peer for some reason is closed
                logging.info(self.resource_manager._log(f"The connection with {peer_id[:6]} is closed"))
                await self.resource_manager._remove_peer(peer_id)

        return Listener(self)

    async def _confirm_download_complete(self):
        saved_pieces = sum(
            piece_status == ResourceManager.PieceStatus.SAVED
            for piece_status in self.piece_status
        )
        assert saved_pieces == len(self.resource.pieces)

        await self.resource_file.accept_download()
        await self.stop_download()
        logging.info(self._log("Download is completed"))

    async def _add_peer(self, peer_id: str, connection: Connection):
        self.connections[peer_id] = connection
        self.bitfields[peer_id] = [False] * len(self.resource.pieces)
        self._free_peers.add(peer_id)

        connection.add_listener(self._create_connection_listener(peer_id))
        await connection.listen()
        # Send the message about the stored pieces
        await self._send_bitfield(connection)

    async def _remove_peer(self, peer_id: str):
        try:
            await self.connections[peer_id].close()
        except Exception as e:
            # Ignore any exception with closing (probably peer_id either is not in list or connection is already closed
            pass
        self.connections.pop(peer_id, None)
        self.bitfields.pop(peer_id, None)
        self._free_peers.discard(peer_id)

    # -----MAIN DOWNLOAD LOGIC BEGINS HERE-----

    async def _download_work(self, peer_id: str, piece_index: int):
        logging.info(self._log(f"Download Work on piece {piece_index} from peer {peer_id[:6]}"))
        connection = self.connections[peer_id]
        await connection.send_message(
            Request(
                piece_index,
                0,
                self.resource.pieces[piece_index].size_bytes
            )
        )
        await asyncio.sleep(60)  # Sleep 1 minute
        if self.piece_status[piece_index] == ResourceManager.PieceStatus.IN_PROGRESS:
            # If after one minute, the piece is still in progress,
            # then something is wrong with peer (slow download speed or smth)
            self._peer_in_charge[piece_index] = ''  # This peer is no more responsible for this piece
            self.piece_status[piece_index] = ResourceManager.PieceStatus.FREE

    async def _download_loop(self):
        logging.info(self._log("Start download loop"))
        works = set()
        while True:
            # Find free pieces
            free_pieces: list[int] = []
            for i, status in enumerate(self.piece_status):
                if status == ResourceManager.PieceStatus.FREE:
                    free_pieces.append(i)

            # Shuffle the pieces
            random.shuffle(free_pieces)

            # Try to find piece and peer that has this piece
            found_work = False
            for piece_index in free_pieces:
                for peer_id in self._free_peers:
                    if self._peer_has_piece(peer_id, piece_index):  # Peer has this piece -> run the work
                        # Update the status and related peer
                        self.piece_status[piece_index] = ResourceManager.PieceStatus.IN_PROGRESS
                        self._peer_in_charge[piece_index] = peer_id

                        task = asyncio.create_task(self._download_work(peer_id, piece_index))
                        task.add_done_callback(lambda t: works.discard(t))
                        works.add(task)

                        found_work = True
                        break
                if found_work:
                    break
            await asyncio.sleep(0.2)

    # -----END OF DOWNLOAD LOGIC-----

    def _peer_has_piece(self, peer_id: str, piece_index: int) -> bool:
        return self.bitfields[peer_id][piece_index] == True

    async def _run_server_task(self, server: asyncio.Server):
        async with server:
            await server.serve_forever()

    # PUBLIC METHODS:
    async def open_public_port(self) -> int:
        # Start accepting peer connections on some random port
        public_server = await asyncio.start_server(
            self._handle_incoming_connection,
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
        if self.has_file:
            raise RuntimeError("Cannot download existing file")

        if self._download_task is None:
            self._download_task = asyncio.create_task(self._download_loop())

    async def stop_download(self):
        logging.info(self._log("Stop download"))

        # Stop downloading the resource
        self._download_task.cancel()
        self._download_task = None

    async def submit_peers(self, peers: list[PeerInfo]):
        for peer in peers:
            if peer.peer_id == self.host_peer_id:
                logging.warning(self._log("host_peer_id is passed in submit_peers"))
                continue

            # IMPORTANT RULE: The initiator of connection is always peer with the smaller id
            if self.host_peer_id < peer.peer_id:
                try:
                    if peer.peer_id not in self.connections:  # We do not want repeating connections
                        connection = await establish_connection(self.host_peer_id, peer, self.resource)
                        await self._add_peer(peer.peer_id, connection)
                        logging.info(self._log(f"Establish connection with {peer.peer_id[:6]}"))
                except Exception:
                    logging.exception(self._log(f"Exception while establishing connection with {peer.peer_id[:6]}"))

    async def start_sharing_file(self):
        self.share_file = True

    async def stop_sharing_file(self):
        self.share_file = False
