import asyncio
from dataclasses import dataclass


class Message:
    """
    A base class for messages that peers exchanges between each other
    """

    # Convert the message object into bytes according to the specs
    def to_bytes(self) -> bytes:
        pass


@dataclass
class Handshake(Message):
    """
    A dataclass for Handshake message
    """
    peer_id: str
    info_hash: str

    def to_bytes(self) -> bytes:
        return "TorrentInno".encode() + bytes.fromhex(self.peer_id) + bytes.fromhex(self.info_hash)


@dataclass
class Request(Message):
    """
    A dataclass for Request (type 1) message
    """
    piece_index: int
    piece_inner_offset: int
    block_length: int

    def to_bytes(self) -> bytes:
        return (
                (13).to_bytes(length=4, byteorder='big') +
                (1).to_bytes(length=1, byteorder='big') +
                self.piece_index.to_bytes(4, byteorder='big') +
                self.piece_inner_offset.to_bytes(4, byteorder='big') +
                self.block_length.to_bytes(4, byteorder='big')
        )


@dataclass
class Piece(Message):
    """
    A dataclass for Piece (type 2) message
    """
    piece_index: int
    piece_inner_offset: int
    block_length: int
    data: bytes

    def __post_init__(self):
        assert len(self.data) == self.block_length

    def to_bytes(self) -> bytes:
        return (
                (13 + len(self.data)).to_bytes(length=4, byteorder='big') +
                (2).to_bytes(length=1, byteorder='big') +
                self.piece_index.to_bytes(4, byteorder='big') +
                self.piece_inner_offset.to_bytes(4, byteorder='big') +
                self.block_length.to_bytes(4, byteorder='big') +
                self.data
        )


@dataclass
class Bitfield(Message):
    """
    A dataclass for Bitfield (type 3) message
    """
    bitfield: list[bool]

    def to_bytes(self) -> bytes:
        result: list[int] = []
        for i in range(0, len(self.bitfield), 8):
            current_byte = 0
            for j in range(i, min(len(self.bitfield), i + 8)):
                if self.bitfield[j]:
                    current_byte += 1 << (i + 7 - j)
            result.append(current_byte)

        return (1 + len(result)).to_bytes(length=4) + (3).to_bytes(length=1) + bytes(result)
