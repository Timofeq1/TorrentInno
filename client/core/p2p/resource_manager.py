import asyncio
import hashlib
from pathlib import Path
from dataclasses import dataclass
import random

from core.common.peer_info import PeerInfo
from core.p2p.connection import Connection, establish_connection
from core.p2p.message import Handshake, Request, Bitfield, Piece
from core.p2p.resource_file import ResourceFile
from core.common.resource import Resource
from core.p2p.connection_listener import ConnectionListener
from enum import Enum
import logging

from core.p2p.resource_save import ResourceSave


class ResourceManager:
    class PieceStatus(Enum):
        FREE = 1  # The piece is not in work
        IN_PROGRESS = 2  # Waiting for reply from some peer
        RECEIVED = 3  # The data has been fetched from network and now is saving on disk
        SAVED = 4  # Piece is successfully saved on disk

    @dataclass
    class State:
        piece_status: list[bool]

    def _log_prefix(self, msg: str) -> str:
        return f"[ResourceManager peer_id={self.host_peer_id[:6]} info_hash={self.info_hash[:6]}] {msg}"

    # Some new peer wants to connect to this peer
    async def _handle_incoming_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        host, port = writer.get_extra_info('peername')
        logging.info(self._log_prefix(f"{host}:{port} is trying to connect"))
        try:
            response = await reader.readexactly(75)
            assert response[0:11].decode() == 'TorrentInno'
            info_hash = response[43:75].hex()
            assert info_hash == self.info_hash

            peer_id: str = response[11:43].hex()

            if self.host_peer_id < peer_id:
                raise RuntimeError(f"Peer {peer_id} has greater id and is trying to establish connection")

            # If we already have connection with this peer id -> abort the incoming connection
            if peer_id in self._connections:
                return

            # If everything is correct, then send the response handshake message
            writer.write(Handshake(peer_id=self.host_peer_id, info_hash=self.info_hash).to_bytes())
            await writer.drain()

            # Create the connection object
            connection = Connection(reader, writer, self.resource)
            await self._add_peer(peer_id, connection)

            logging.info(self._log_prefix(f"Establish connection with {peer_id[:6]}"))
        except Exception as e:
            logging.exception(self._log_prefix(f"Failed to handle incoming connection with {host}"))
            writer.close()
            await writer.wait_closed()

    def _create_connection_listener(self, peer_id: str) -> ConnectionListener:
        return ConnectionListenerImpl(peer_id, self)

    async def _confirm_download_complete(self):
        saved_pieces = sum(
            piece_status == ResourceManager.PieceStatus.SAVED
            for piece_status in self.piece_status
        )
        assert saved_pieces == len(self.resource.pieces)

        await self.resource_file.accept_download()
        await self.stop_download()
        await self.resource_save.remove_save()
        logging.info(self._log_prefix("Download is completed"))

    async def _add_peer(self, peer_id: str, connection: Connection):
        self._connections[peer_id] = connection
        self._bitfields[peer_id] = [False] * len(self.resource.pieces)
        self._free_peers.add(peer_id)

        connection.add_listener(self._create_connection_listener(peer_id))
        await connection.listen()
        # Send the message about the stored pieces
        await self._send_bitfield(peer_id)

    async def _remove_peer(self, peer_id: str):
        try:
            await self._connections[peer_id].close()
        except Exception as e:
            # Ignore any exception with closing (probably peer_id either is not in list or connection is already closed
            pass
        self._connections.pop(peer_id, None)
        self._bitfields.pop(peer_id, None)
        self._free_peers.discard(peer_id)

    # -----MAIN DOWNLOAD LOGIC BEGINS HERE-----

    async def _download_work(self, peer_id: str, piece_index: int):
        logging.info(self._log_prefix(f"Download Work on piece {piece_index} from peer {peer_id[:6]}"))
        connection = self._connections[peer_id]
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
        logging.info(self._log_prefix("Start download loop"))
        works = set()
        while True:
            # Find free pieces
            free_pieces: list[int] = []
            saved_pieces = 0
            for i, status in enumerate(self.piece_status):
                if status == ResourceManager.PieceStatus.FREE:
                    free_pieces.append(i)
                if status == ResourceManager.PieceStatus.SAVED:
                    saved_pieces += 1

            if saved_pieces == len(self.resource.pieces):
                break

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
        return self._bitfields[peer_id][piece_index] == True

    def _get_bitfield(self) -> list[bool]:
        return list(
            piece_status == ResourceManager.PieceStatus.SAVED for piece_status in self.piece_status
        )

    async def _save_loading_state(self):
        try:
            await self.resource_save.write_bitfield(self._get_bitfield())
        except Exception:
            logging.exception(self._log_prefix("Can't save bitfield"))

    async def _send_bitfield(self, peer_id: str):
        connection = self._connections[peer_id]
        bitfield = Bitfield(self._get_bitfield())
        await connection.send_message(bitfield)

    async def _send_bitfield_to_all_peers(self):
        bitfield = Bitfield(self._get_bitfield())
        await asyncio.gather(
            *(connection.send_message(bitfield)
              for connection in self._connections.values()),
            return_exceptions=True
        )

    # Periodic broadcast with bitfield to compensate possible exceptions in the Piece message
    async def _periodic_broadcast(self):
        while True:
            await self._send_bitfield_to_all_peers()
            await asyncio.sleep(30)  # Sleep for 30 seconds

    async def _serve_forever(self, server: asyncio.Server):
        async with server:
            await server.serve_forever()

    def __init__(
            self,
            host_peer_id: str,
            destination: Path,
            resource: Resource,
    ):
        """
        Create a new ResourceManager instance

        :param host_peer_id: the peer_id that will host the resource
        :param destination: The destination of the file on the filesystem. Important: if the destination exists
        on the moment the class is instantiated, then it's assumed that the caller has the `destination` file
        and therefore the file will only be shared (and not downloaded)
        :param resource: the resource class representing the class to be uploaded/downloaded
        """
        self.host_peer_id = host_peer_id
        self.destination = destination
        self.resource = resource

        self.info_hash = resource.get_info_hash()

        # Save state for resource
        self.resource_save = ResourceSave(destination, resource)

        # If the peer can give file pieces
        self.share_file = False

        # Peer dictionaries
        self._connections: dict[str, Connection] = dict()  # peer_id <-> Connection
        self._bitfields: dict[str, list[bool]] = dict()  # peer_id <-> bitfield (owned chunks)
        self._free_peers: set[str] = set()  # set of peer ids that are not involved in any work

        self.piece_status: list[ResourceManager.PieceStatus] = []

        has_file = destination.exists()

        if has_file:  # The caller claims to already have the file
            self.resource_file = ResourceFile(
                destination,
                resource,
                fresh_install=False,
                initial_state=ResourceFile.State.DOWNLOADED
            )
            self.piece_status = [ResourceManager.PieceStatus.SAVED] * len(self.resource.pieces)
        else:  # The caller does not the complete downloaded file
            self.resource_file = ResourceFile(
                destination,
                resource,
                fresh_install=False,
                initial_state=ResourceFile.State.DOWNLOADING
            )
            self.piece_status = [ResourceManager.PieceStatus.FREE] * len(self.resource.pieces)

        # Current peer id that handles the piece (empty string=no peer)
        self._peer_in_charge: list[str] = [''] * len(self.resource.pieces)

        # Various asyncio background tasks
        self._download_task: asyncio.Task | None = None
        self._server_task: asyncio.Task | None = None
        self._broadcast_task: asyncio.Task | None = None

    # PUBLIC METHODS:
    async def open_public_port(self) -> int:
        """
        Opens a new socket that will be used to accept incoming connections from other peers

        :return: port on which the new socket is opened
        """
        if self._server_task is not None:
            raise RuntimeError("Peer is already accepting connections")

        # Start accepting peer connections on some random port
        public_server = await asyncio.start_server(
            self._handle_incoming_connection,
            host='0.0.0.0',
            port=0
        )
        host, port = public_server.sockets[0].getsockname()
        self._server_task = asyncio.create_task(self._serve_forever(public_server))

        # Also run the bitfield broadcast task
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._periodic_broadcast())

        # Return port on which connection has been opened
        return port

    async def close_public_port(self):
        """
        Closes the socket that accepts the new connections (NOTE: after calling this method, the old port received in
        `open_public_port` cannot be reused anymore as this port is received randomly from the OS)
        """
        # Close the server_task connection
        if self._server_task is not None:
            self._server_task.cancel()
            self._server_task = None

        if self._broadcast_task is not None:
            self._broadcast_task.cancel()
            self._broadcast_task = None

    async def restore_previous(self):
        """
        Attempts to restore the saved state and start download with this state (for example, to get which pieces
        are already downloaded in order to not repeat the download work).

        NOTE: If the destination file exists, then this method
        assumes that the file is already completely downloaded
        (and so sets the status of all pieces as SAVED (or downloaded))
        """
        if self.destination.exists():
            self.piece_status = [ResourceManager.PieceStatus.SAVED] * len(self.resource.pieces)
            self._peer_in_charge = [''] * len(self.resource.pieces)
            return

        try:
            bitfield = await self.resource_save.read_bitfield()
            for i in range(len(self.piece_status)):
                if bitfield[i]:
                    self.piece_status[i] = ResourceManager.PieceStatus.SAVED
                    self._peer_in_charge[i] = ''
            logging.info(self._log_prefix(f"Restored bitfield: {bitfield}"))
        except Exception as e:
            logging.info(self._log_prefix(f"Failed to read bitfield: {e}"))

    async def start_download(self):
        """
        Start downloading the file. If the destination file already exists, then this method does nothing. The file
        will usually be downloaded into a specifically named temporary file located at the same folder as `destination`.
        Once the ResourceManager detects, that the file is completely downloaded
        it terminates the download and renames the temporary file into the `destination`.
        """
        if self.destination.exists():
            return

        if self._download_task is None:
            self._download_task = asyncio.create_task(self._download_loop())

    async def stop_download(self):
        """
        Stop downloading the file.
        """
        logging.info(self._log_prefix("Stop download"))

        if self._download_task is not None:
            # Stop downloading the resource
            self._download_task.cancel()
            self._download_task = None

    async def start_sharing_file(self):
        """
        Sets the flags that allows ResourceManager to share file (file pieces) with other peers.
        This is the default behaviour.
        """
        self.share_file = True

    async def stop_sharing_file(self):
        """
        Forbid the ResourceManager to share file (file pieces) with other peers.
        """
        self.share_file = False

    async def full_start(self) -> int:
        """
        A convenience methods that automatically opens the public port of the resource manager,
        starts download, attempt to restore the previous download state etc.

        :return: the same as `open_public_port()`
        """
        await self.restore_previous()
        await self.start_sharing_file()
        await self.start_download()
        listen_port = await self.open_public_port()
        return listen_port

    async def shutdown(self):
        """
        A convenience method that is the opposite of `full_start()` (i.e. close everything that was started/launched)
        """
        await self.close_public_port()
        await asyncio.gather(
            *(connection.close() for connection in self._connections.values()),
            return_exceptions=True
        )
        await self.stop_download()
        await self.stop_sharing_file()

    async def submit_peers(self, peers: list[PeerInfo]):
        """
        The only way to tell ResourceManager about peers related to the resource. Usually these will be the peers fetched
        from the tracker response on announce request with the *same* info hash as the RequestManager was created with.

        :param peers: The list of peers known to be related with the resource
        """
        for peer in peers:
            if peer.peer_id == self.host_peer_id:
                logging.warning(self._log_prefix("host_peer_id is passed in submit_peers"))
                continue

            # IMPORTANT RULE: The initiator of connection is always peer with the smaller id
            if self.host_peer_id < peer.peer_id:
                try:
                    if peer.peer_id not in self._connections:  # We do not want repeating connections
                        connection = await establish_connection(self.host_peer_id, peer, self.resource)
                        await self._add_peer(peer.peer_id, connection)
                        logging.info(self._log_prefix(f"Establish connection with {peer.peer_id[:6]}"))
                except Exception:
                    logging.exception(
                        self._log_prefix(f"Exception while establishing connection with {peer.peer_id[:6]}"))

    async def get_state(self) -> 'ResourceManager.State':
        """
        Get the current state of the resource (i.e. downloaded pieces, upload/download speed etc.)
        :return: The current state of the resource (file)
        """
        return ResourceManager.State(self._get_bitfield())


class ConnectionListenerImpl(ConnectionListener):
    def __init__(self, connected_peer_id: str, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        self.connected_peer_id = connected_peer_id

    def _info_log(self, msg: str):
        logging.info(
            self.resource_manager._log_prefix(msg)
        )

    async def on_request(self, request: Request):
        if not self.resource_manager.share_file:
            self._info_log(f"Ignore Request message from peer {self.connected_peer_id[:6]} as sharing is disabled")
            return

        try:
            data = await self.resource_manager.resource_file.get_block(
                request.piece_index,
                request.piece_inner_offset,
                request.block_length
            )
            connection = self.resource_manager._connections[self.connected_peer_id]
            await connection.send_message(
                Piece(
                    request.piece_index,
                    request.piece_inner_offset,
                    request.block_length,
                    data
                )
            )
            self._info_log(f"Send piece {request.piece_index} on Request message to peer {self.connected_peer_id[:6]}")
        except Exception:
            logging.exception(
                self.resource_manager._log_prefix(
                    f"Exception on request message from peer {self.connected_peer_id[:6]}"
                )
            )
            pass

    async def on_piece(self, piece: Piece):
        # This peer is not in charge on this piece
        if self.resource_manager._peer_in_charge[piece.piece_index] != self.connected_peer_id:
            self._info_log(f"Discard piece {piece.piece_index} from {self.connected_peer_id[:6]} as not in charge")
            return
        self.resource_manager.piece_status[piece.piece_index] = ResourceManager.PieceStatus.RECEIVED
        try:
            # Check that the received piece matches the hash
            expected_hash = hashlib.sha256(piece.data).hexdigest()
            received_hash = self.resource_manager.resource.pieces[piece.piece_index].sha256

            if expected_hash != received_hash:
                logging.warning(
                    self.resource_manager._log_prefix(
                        f"Incorrect hash of piece {piece.piece_index} on Piece message from peer {self.connected_peer_id}\n" +
                        f"Expected: {expected_hash}\n"
                        f"Received: {received_hash}"
                    )
                )
                return

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
            self._info_log(f"Save piece {piece.piece_index} from {self.connected_peer_id[:6]}")

            # Also update the information about saved piece in the file:
            await self.resource_manager._save_loading_state()

            if saved_pieces == len(self.resource_manager.resource.pieces):
                # The file is successfully downloaded!
                try:
                    await self.resource_manager._confirm_download_complete()
                except Exception:
                    logging.exception(self.resource_manager._log_prefix("Cannot complete download"))

            await self.resource_manager._send_bitfield_to_all_peers()
        except Exception:
            logging.exception(
                self.resource_manager._log_prefix(
                    f"Exception on piece message from peer {self.connected_peer_id[:6]}"
                )
            )
            self.resource_manager.piece_status[piece.piece_index] = ResourceManager.PieceStatus.FREE
            pass

    async def on_bitfield(self, bitfield: Bitfield):
        self.resource_manager._bitfields[self.connected_peer_id] = bitfield.bitfield
        self._info_log(f"Bitfield from {self.connected_peer_id[:6]}: {bitfield.bitfield}")

    async def on_close(self, cause):
        # The connection with peer for some reason is closed
        self._info_log(f"The connection with {self.connected_peer_id[:6]} is closed")
        await self.resource_manager._remove_peer(self.connected_peer_id)
