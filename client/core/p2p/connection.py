import asyncio

from core.common.peer_info import PeerInfo
from core.p2p.connection_listener import ConnectionListener
from core.p2p.message import Request, Piece, Handshake, Message, Bitfield
from core.common.resource import Resource


class Connection:
    """
    Represents a resource-related connection between two peers.
    The class works with asyncio, therefore its methods must be called on a thread with running event loop
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, resource: Resource):
        self.reader = reader
        self.writer = writer
        self.listeners: list[ConnectionListener] = []
        self.resource = resource

        self._listen_on_reader_task: asyncio.Task | None = None

    def add_listener(self, listener: ConnectionListener):
        self.listeners.append(listener)

    def remove_listener(self, listener: ConnectionListener):
        self.listeners.remove(listener)

    # Read big int from the saved reader
    async def _read_int_big_endian(self, length: int) -> int:
        return int.from_bytes(await self.reader.readexactly(length))

    # Launch infinite loop to fetch messages from the reader and notify the listeners
    async def _listen_on_reader(self):
        try:
            while True:
                message_length = await self._read_int_big_endian(4)
                message_type = await self._read_int_big_endian(1)

                if message_type == 1:
                    # Request message

                    # Parse the message
                    piece_index = await self._read_int_big_endian(4)
                    piece_inner_offset = await self._read_int_big_endian(4)
                    block_length = await self._read_int_big_endian(4)

                    request = Request(piece_index, piece_inner_offset, block_length)

                    # Notify listeners
                    await asyncio.gather(
                        *(listener.on_request(request) for listener in self.listeners),
                        return_exceptions=True
                    )
                elif message_type == 2:
                    # Piece message

                    # Parse the message
                    piece_index = await self._read_int_big_endian(4)
                    piece_inner_offset = await self._read_int_big_endian(4)
                    block_length = await self._read_int_big_endian(4)

                    if block_length > 10 ** 6:
                        raise RuntimeError("The length of data exceeded 1 MB")

                    # Retrieve the data block
                    data = await self.reader.readexactly(block_length)

                    piece = Piece(piece_index, piece_inner_offset, block_length, data)

                    # Notify the listeners
                    await asyncio.gather(
                        *(listener.on_piece(piece) for listener in self.listeners),
                        return_exceptions=True
                    )
                elif message_type == 3:
                    # Bitfield message

                    # Parse the message
                    bytes_parsed = await self.reader.readexactly(
                        len(self.resource.pieces) // 8 + bool(len(self.resource.pieces) % 8)
                    )

                    bitfield = Bitfield(bitfield=[False] * len(self.resource.pieces))
                    for i in range(0, len(self.resource.pieces)):
                        has_piece_i = bool((bytes_parsed[i // 8] >> (7 - i % 8)) & 1)
                        bitfield.bitfield[i] = has_piece_i

                    # Notify the listeners
                    await asyncio.gather(
                        *(listener.on_bitfield(bitfield) for listener in self.listeners),
                        return_exceptions=True
                    )

        except Exception as e:
            # For now close the connection in case of any exception
            await asyncio.gather(
                *(listener.on_close(e) for listener in self.listeners),
                return_exceptions=True
            )
        finally:
            self.writer.close()
            await self.writer.wait_closed()

    async def send_message(self, message: Message):
        self.writer.write(message.to_bytes())
        await self.writer.drain()

    async def listen(self):
        if self._listen_on_reader_task is None:
            loop = asyncio.get_running_loop()
            self._listen_on_reader_task = loop.create_task(self._listen_on_reader())

    async def close(self):
        if self._listen_on_reader_task is not None:
            self._listen_on_reader_task.cancel()
            self._listen_on_reader_task = None
            self.writer.close()
            await self.writer.wait_closed()


# Create the connection with some peer
async def establish_connection(
        host_peer_id: str,
        destination_peer: PeerInfo,
        resource: Resource
) -> Connection:
    reader, writer = await asyncio.open_connection(destination_peer.public_ip, destination_peer.public_port)

    info_hash = resource.get_info_hash()
    handshake = Handshake(host_peer_id, info_hash)
    try:
        writer.write(handshake.to_bytes())
        response = await reader.readexactly(75)
        assert response[0:11].decode() == 'TorrentInno'
        assert response[11:43].hex() == destination_peer.peer_id
        assert response[43:75].hex() == info_hash
    except Exception:
        writer.close()
        await writer.wait_closed()
        raise  # re-raise the error

    return Connection(reader, writer, resource)