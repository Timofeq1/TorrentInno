import asyncio

import pytest

from core.p2p.connection import Connection
from core.p2p.connection_listener import ConnectionListener
from core.p2p.message import Piece, Request, Bitfield
from core.tests.mocks import mock_resource, mock_request, mock_piece, mock_bitfield
from core.common.resource import Resource


async def get_connections(resource: Resource) -> (Connection, Connection):
    queue = asyncio.Queue()

    async def handle_client(reader, writer):
        await queue.put((reader, writer))

    server = await asyncio.start_server(handle_client, '127.0.0.1', 0)
    host, port = server.sockets[0].getsockname()
    client_reader, client_writer = await asyncio.open_connection(host, port)
    server_reader, server_writer = await queue.get()

    client_connection = Connection(client_reader, client_writer, resource)
    server_connection = Connection(server_reader, server_writer, resource)
    return client_connection, server_connection


@pytest.mark.asyncio
async def test_connection():
    connections = await get_connections(mock_resource)
    sender: Connection = connections[0]
    receiver: Connection = connections[1]

    class SenderListener(ConnectionListener):
        async def on_piece(self, piece: Piece):
            print(piece)
            assert piece == mock_piece

        async def on_bitfield(self, bitfield: Bitfield):
            print(bitfield)
            assert bitfield == mock_bitfield

        async def on_close(self, cause):
            print(f"SenderListener; onClose: {cause}")

    class ReceiverListener(ConnectionListener):
        async def on_request(self, request: Request) -> bytes:
            print(request)
            assert request == mock_request
            return b''

        async def on_close(self, cause):
            print(f"ReceiverListener; onClose: {cause}")

    sender.add_listener(SenderListener())
    receiver.add_listener(ReceiverListener())

    await receiver.listen()
    await sender.listen()

    await sender.send_message(mock_request)
    await receiver.send_message(mock_piece)
    await receiver.send_message(mock_bitfield)

