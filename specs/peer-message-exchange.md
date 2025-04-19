# Peer message exchange format

All messages between peers are translated as raw bytes. 
Where applicable, the order of bytes is big-endian.
All indexes are zero based, unless stated otherwise.
The peer-id is a string satisfying regex `^[0-9a-zA-Z]{64}$`

## Handshake
```
TorrentInno[peer-id (8 bytes)][info-hash (64 bytes)]
```
*Example*:
```
TorrentInnouQ5dKnR3FZcAVjY0eBHwGslM9tJpXxUNq7PavCLOgmy6z1nEkWYh8b2rTcfMVuDl2c74fd17edafd80e8447b0d46741ee243b7eb74c1a1e41e2c7b7afecb5a4b96f3c6e5d7cb8e5b7e20d2343fdb1f3e22f3efb2c4ff977d7dbd7d0e351b9d4a2c4
```

**Description**:
The handshake message is sent by one of the peers trying to establish a connection with some other peer. Note that the length of the handshake message is always fixed.

The `info-hash` is the hash of the `torrentinno` file.

The peer that receives this message must check if it knows the resource in the `info-hash` field. If it knows this resource, then reply will the same message, substituting `peer-id` with its own id.

If the handshake is successful, then both peers create and maintain a separate connection tied to that specific resource. The connection is biderectional continuous channel where peers exchange length-prefixed messages.

## Peer to peer communication

Each message has the following format: `[body-length (8 bytes)][message-body]`. Where `body-length` is the length of the `[message-body]` (in bytes). Further, only `[message-body]` will be discussed.

Each `[message-body]` has the following format: `[message-type (1 byte)][message-data]`. `[message-type]` is a number (`0x1`, for example)
Currently, only two types of messages are supported:
1) 'Request':  The `[message-data]` has format: `[piece-index (8 bytes)][piece-inner-offset (8 bytes)][block-length (8 bytes)]`. 
This message indicates that the peer wants to fetch the `[block-length]` bytes from the piece with index `[piece-index]`, with inner offset within the piece of length `[piece-inner-offset]` bytes. 


2) 'Piece': The `[message-data]` has format: `[piece-index (8 bytes)][piece-inner-offset (8 bytes)][block-length (8 bytes)]data`. The first three fields has the same meaning as in the 'Request' message. The `data` contains the requested part of the file and it must have the length of `block-length` bytes.

*Example:*
The full message to request 1024 bytes with offset 384 bytes offset within the piece 19 looks like this:

`0x00000019` `0x1` `0x00000013` `0x00000180` `0x00000400`

References:
[https://www.bittorrent.org/beps/bep_0003.html](https://www.bittorrent.org/beps/bep_0003.html)
