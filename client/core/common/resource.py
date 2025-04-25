import datetime
from dataclasses import dataclass
import json
import hashlib


@dataclass
class Resource:
    @dataclass
    class Piece:
        sha256: str
        size_bytes: int

    tracker_ip: str
    tracker_port: int
    comment: str
    creation_date: datetime.datetime
    name: str
    pieces: list[Piece]

    def get_info_hash(self) -> str:
        resource_repr = f"{self.tracker_ip}{self.tracker_port}{self.comment}{self.creation_date.isoformat()}{self.name}{self.pieces}"
        info_hash = hashlib.sha256(resource_repr.encode(encoding='utf-8')).hexdigest()
        return info_hash
