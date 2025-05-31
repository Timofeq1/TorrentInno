from dataclasses import dataclass


@dataclass
class PeerInfo:
    public_ip: str
    public_port: int
    peer_id: str