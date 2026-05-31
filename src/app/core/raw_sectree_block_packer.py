from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from app.core.attr_compatibility_mapper import map_attr_value_to_dword
from app.core.attr_parser import parse_attr_file
from app.core.coordinate import geometry_from_setting
from app.core.map_reader import MapSource
from app.core.server_attr_analyzer import (
    analyze_server_attr_file,
    find_matching_server_attr_sample,
)


DWORDS_PER_SECTREE = 128 * 128
RAW_BYTES_PER_SECTREE = DWORDS_PER_SECTREE * 4


def build_raw_sectree_dword_blocks(map_source: MapSource) -> list[list[int]]:
    return build_raw_sectree_dword_blocks_with_profile(map_source, mapping_profile="candidate_v1")


def build_raw_sectree_dword_blocks_with_profile(
    map_source: MapSource,
    mapping_profile: str = "candidate_v1",
) -> list[list[int]]:
    geometry = geometry_from_setting(map_source.setting)
    attr_tiles = _load_attr_tiles(map_source)
    scale = _resolve_scale(map_source, geometry)
    total_block_count = geometry.sectree_width * geometry.sectree_height
    return [
        _build_block_dwords(
            attr_tiles,
            block_x=block_index % geometry.sectree_width,
            block_y=block_index // geometry.sectree_width,
            scale=scale,
            mapping_profile=mapping_profile,
        )
        for block_index in range(total_block_count)
    ]


def pack_raw_sectree_block_bytes(map_source: MapSource) -> list[bytes]:
    return pack_raw_sectree_block_bytes_with_profile(map_source, mapping_profile="candidate_v1")


def pack_raw_sectree_block_bytes_with_profile(
    map_source: MapSource,
    mapping_profile: str = "candidate_v1",
) -> list[bytes]:
    return [
        struct.pack(f"<{len(dwords)}I", *dwords)
        for dwords in build_raw_sectree_dword_blocks_with_profile(
            map_source,
            mapping_profile=mapping_profile,
        )
    ]


def build_raw_sectree_block_report(
    map_source: MapSource,
    sample_block_limit: int = 4,
    sample_dword_limit: int = 16,
    sample_root: str | Path | None = None,
) -> dict:
    geometry = geometry_from_setting(map_source.setting)
    attr_tiles = _load_attr_tiles(map_source)
    scale = _resolve_scale(map_source, geometry)
    total_block_count = geometry.sectree_width * geometry.sectree_height

    sample_blocks: list[dict] = []
    for block_index in range(min(sample_block_limit, total_block_count)):
        block_x = block_index % geometry.sectree_width
        block_y = block_index // geometry.sectree_width
        sample_blocks.append(
            _build_block_sample(
                attr_tiles,
                geometry.sectree_width,
                block_x,
                block_y,
                scale,
                sample_dword_limit,
            )
        )

    report = {
        "map_name": map_source.name,
        "sectree_grid": {
            "width": geometry.sectree_width,
            "height": geometry.sectree_height,
        },
        "total_block_count": total_block_count,
        "dwords_per_block": DWORDS_PER_SECTREE,
        "raw_bytes_per_block": RAW_BYTES_PER_SECTREE,
        "total_raw_uncompressed_bytes": total_block_count * RAW_BYTES_PER_SECTREE,
        "scale_factor": scale,
        "sample_block_limit": min(sample_block_limit, total_block_count),
        "sample_blocks": sample_blocks,
    }

    if sample_root is not None:
        sample_path = find_matching_server_attr_sample(map_source.name, sample_root)
        if sample_path is not None:
            sample = analyze_server_attr_file(sample_path)
            report["server_attr_reference"] = {
                "path": str(sample.path),
                "compressed_size": sample.size,
                "compressed_block_count": sample.block_count,
                "sectree_width": sample.sectree_width,
                "sectree_height": sample.sectree_height,
                "block_count_matches": sample.block_count == total_block_count,
            }

    return report


def build_batch_raw_sectree_block_summary(
    map_sources: list[MapSource],
    sample_root: str | Path | None = None,
) -> dict:
    maps: list[dict] = []
    total_raw_bytes = 0
    first_block_checksums: Counter[str] = Counter()

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        try:
            report = build_raw_sectree_block_report(
                map_source,
                sample_block_limit=1,
                sample_dword_limit=16,
                sample_root=sample_root,
            )
        except ValueError:
            continue

        total_raw_bytes += report["total_raw_uncompressed_bytes"]
        first_block = report["sample_blocks"][0] if report["sample_blocks"] else None
        if first_block is not None:
            first_block_checksums[first_block["md5"]] += 1

        item = {
            "map_name": report["map_name"],
            "total_block_count": report["total_block_count"],
            "total_raw_uncompressed_bytes": report["total_raw_uncompressed_bytes"],
            "first_block": first_block,
        }
        if "server_attr_reference" in report:
            item["server_attr_reference"] = report["server_attr_reference"]
        maps.append(item)

    return {
        "map_count": len(maps),
        "total_raw_uncompressed_bytes": total_raw_bytes,
        "top_first_block_checksums": [
            {"md5": checksum, "map_count": count}
            for checksum, count in first_block_checksums.most_common(12)
        ],
        "maps": maps,
    }


def write_raw_sectree_block_report(
    map_source: MapSource,
    output_path: str | Path,
    sample_block_limit: int = 4,
    sample_dword_limit: int = 16,
    sample_root: str | Path | None = None,
) -> Path:
    report = build_raw_sectree_block_report(
        map_source,
        sample_block_limit=sample_block_limit,
        sample_dword_limit=sample_dword_limit,
        sample_root=sample_root,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def write_batch_raw_sectree_block_summary(
    map_sources: list[MapSource],
    output_path: str | Path,
    sample_root: str | Path | None = None,
) -> Path:
    summary = build_batch_raw_sectree_block_summary(map_sources, sample_root=sample_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def _build_block_sample(
    attr_tiles: dict[tuple[int, int], bytes],
    sectree_width: int,
    block_x: int,
    block_y: int,
    scale: int,
    sample_dword_limit: int,
) -> dict:
    dwords = _build_block_dwords(attr_tiles, block_x, block_y, scale)
    raw_bytes = struct.pack(f"<{len(dwords)}I", *dwords)
    counter = Counter(dwords)
    dominant_dword, dominant_count = counter.most_common(1)[0]

    return {
        "block_index": block_y * sectree_width + block_x,
        "block_x": block_x,
        "block_y": block_y,
        "raw_byte_length": len(raw_bytes),
        "md5": hashlib.md5(raw_bytes).hexdigest(),
        "dominant_dword": dominant_dword,
        "dominant_hex": f"0x{dominant_dword:08X}",
        "dominant_share": _ratio(dominant_count, DWORDS_PER_SECTREE),
        "unique_dword_count": len(counter),
        "first_dwords": [f"0x{value:08X}" for value in dwords[:sample_dword_limit]],
        "top_dwords": [
            {
                "dword": value,
                "hex": f"0x{value:08X}",
                "count": count,
                "share": _ratio(count, DWORDS_PER_SECTREE),
            }
            for value, count in counter.most_common(8)
        ],
    }


def _build_block_dwords(
    attr_tiles: dict[tuple[int, int], bytes],
    block_x: int,
    block_y: int,
    scale: int,
    mapping_profile: str = "candidate_v1",
) -> list[int]:
    dwords: list[int] = []
    base_x = block_x * 128
    base_y = block_y * 128

    for local_y in range(128):
        for local_x in range(128):
            server_x = base_x + local_x
            server_y = base_y + local_y
            attr_x = server_x // scale
            attr_y = server_y // scale
            attr_value = _get_attr_value(attr_tiles, attr_x, attr_y)
            dwords.append(map_attr_value_to_dword(attr_value, mapping_profile))

    return dwords


def _load_attr_tiles(map_source: MapSource) -> dict[tuple[int, int], bytes]:
    tiles: dict[tuple[int, int], bytes] = {}
    for attr_file in map_source.attr_files:
        parsed = parse_attr_file(attr_file)
        coord = (int(attr_file.parent.name[:3]), int(attr_file.parent.name[3:]))
        tiles[coord] = parsed.payload
    return tiles


def _resolve_scale(map_source: MapSource, geometry) -> int:
    attr_width = map_source.setting.width * 256
    attr_height = map_source.setting.height * 256
    if attr_width == 0 or attr_height == 0:
        raise ValueError(f"Attr grid olusturulamadi: {map_source.name}")

    server_width = geometry.sectree_width * geometry.cells_per_sectree_axis
    server_height = geometry.sectree_height * geometry.cells_per_sectree_axis
    scale_x = server_width // attr_width
    scale_y = server_height // attr_height
    if scale_x <= 0 or scale_y <= 0 or scale_x != scale_y:
        raise ValueError(
            f"Tutarsiz attr->server olcegi: {map_source.name} ({scale_x}, {scale_y})"
        )
    return scale_x


def _get_attr_value(
    attr_tiles: dict[tuple[int, int], bytes],
    attr_x: int,
    attr_y: int,
) -> int:
    tile_x = attr_x // 256
    tile_y = attr_y // 256
    local_x = attr_x % 256
    local_y = attr_y % 256
    payload = attr_tiles.get((tile_x, tile_y))
    if payload is None:
        return 0
    return payload[local_y * 256 + local_x]


def _ratio(left: int, right: int) -> float:
    if right == 0:
        return 0.0
    return round(left / right, 6)
