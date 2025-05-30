import datetime

from core.p2p.message import Request, Piece, Bitfield
from core.common.resource import Resource

mock_resource = Resource(
    tracker_ip="127.0.0.1",
    tracker_port=8080,
    comment="Test torrent for unit testing",
    creation_date=datetime.datetime(2025, 4, 26, 15, 30, 0),
    name="sample_file.txt",
    pieces=[
        Resource.Piece(sha256="a" * 64, size_bytes=512),
        Resource.Piece(sha256="b" * 64, size_bytes=1500),
        Resource.Piece(sha256="c" * 64, size_bytes=768)
    ]
)

mock_request = Request(
    piece_index=1,
    piece_inner_offset=100 * 200,
    block_length=1337
)

mock_piece = Piece(
    piece_index=0,
    piece_inner_offset=400,
    block_length=64,
    data=b'a' * 64
)

mock_bitfield = Bitfield(
    bitfield=[False, True]
)
