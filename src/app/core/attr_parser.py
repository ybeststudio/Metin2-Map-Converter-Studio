from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ATTR_TILE_SIZE = 256
ATTR_HEADER_SIZE = 6
ATTR_PAYLOAD_SIZE = ATTR_TILE_SIZE * ATTR_TILE_SIZE
ATTR_FILE_SIZE = ATTR_HEADER_SIZE + ATTR_PAYLOAD_SIZE


@dataclass(slots=True)
class AttrTile:
    path: Path
    header: bytes
    payload: bytes

    @property
    def payload_size(self) -> int:
        return len(self.payload)

    @property
    def unique_values(self) -> list[int]:
        return sorted(set(self.payload))

    @property
    def most_common_values(self) -> list[tuple[int, int]]:
        return Counter(self.payload).most_common(8)


def parse_attr_file(file_path: str | Path) -> AttrTile:
    path = Path(file_path)
    data = path.read_bytes()
    if len(data) != ATTR_FILE_SIZE:
        raise ValueError(
            f"Beklenmeyen attr.atr boyutu: {path} -> {len(data)} byte"
        )

    return AttrTile(
        path=path,
        header=data[:ATTR_HEADER_SIZE],
        payload=data[ATTR_HEADER_SIZE:],
    )
