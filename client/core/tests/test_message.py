from core.p2p.message import Handshake, Request, Piece, Bitfield


def test_handshake_to_bytes():
    peer_id = 'aabbccddeeff00112233445566778899'
    info_hash = '99887766554433221100ffeeddccbbaa'
    handshake = Handshake(peer_id, info_hash)
    expected = (
            b'TorrentInno' +
            bytes.fromhex(peer_id) +
            bytes.fromhex(info_hash)
    )
    assert handshake.to_bytes() == expected


def test_request_to_bytes():
    request = Request(10, 1024, 500)
    expected = (
            (13).to_bytes(4) +
            (1).to_bytes(1) +
            request.piece_index.to_bytes(4) +
            request.piece_inner_offset.to_bytes(4) +
            request.block_length.to_bytes(4)
    )
    assert request.to_bytes() == expected


def test_piece_to_bytes():
    piece = Piece(10, 1024, 4, b'102b')
    expected = (
            (17).to_bytes(4) +
            (2).to_bytes(1) +
            piece.piece_index.to_bytes(4, 'big') +
            piece.piece_inner_offset.to_bytes(4, 'big') +
            piece.block_length.to_bytes(4, 'big') +
            piece.data
    )
    assert piece.to_bytes() == expected


def test_bitfield_to_bytes():
    bitfield = Bitfield([True, True, False, False, True, True, True, False, True, False])
    expected = (
        (3).to_bytes(4) +
        (3).to_bytes(1) +
        bytes([206, 128])
    )

    assert bitfield.to_bytes() == expected
