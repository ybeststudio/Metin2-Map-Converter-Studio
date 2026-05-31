from __future__ import annotations

import json
from collections import Counter
import struct
from dataclasses import dataclass
from pathlib import Path

from app.core.attr_parser import parse_attr_file
from app.core.coordinate import geometry_from_setting
from app.core.map_reader import MapSource

try:
    import lzo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    lzo = None


RAW_BYTES_PER_SECTREE = 128 * 128 * 4


@dataclass(slots=True)
class ServerAttrSample:
    path: Path
    size: int
    sectree_width: int
    sectree_height: int
    block_sizes: list[int]

    @property
    def block_count(self) -> int:
        return len(self.block_sizes)

    @property
    def first_block_sizes(self) -> list[int]:
        return self.block_sizes[:8]

    @property
    def block_size_stats(self) -> dict:
        if not self.block_sizes:
            return {"min": 0, "max": 0, "avg": 0.0}
        return {
            "min": min(self.block_sizes),
            "max": max(self.block_sizes),
            "avg": round(sum(self.block_sizes) / len(self.block_sizes), 3),
        }


def is_lzo_backend_available() -> bool:
    return lzo is not None


def analyze_server_attr_file(file_path: str | Path) -> ServerAttrSample:
    path = Path(file_path)
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"Server_attr dosyasi cok kucuk: {path}")

    sectree_width = struct.unpack_from("<I", data, 0)[0]
    sectree_height = struct.unpack_from("<I", data, 4)[0]
    offset = 8
    block_sizes: list[int] = []

    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError(
                f"Server_attr blok basligi yarim kalmis: {path} @ {offset}"
            )
        block_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if offset + block_size > len(data):
            raise ValueError(
                f"Server_attr blok boyutu gecersiz: {path} @ {offset} size={block_size}"
            )
        block_sizes.append(block_size)
        offset += block_size

    return ServerAttrSample(
        path=path,
        size=len(data),
        sectree_width=sectree_width,
        sectree_height=sectree_height,
        block_sizes=block_sizes,
    )


def validate_server_attr_lzo_blocks(
    file_path: str | Path,
    block_limit: int = 8,
) -> dict:
    if lzo is None:
        return {
            "lzo_backend_available": False,
            "validated_block_count": 0,
            "blocks": [],
        }

    path = Path(file_path)
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"Server_attr dosyasi cok kucuk: {path}")

    sectree_width = struct.unpack_from("<I", data, 0)[0]
    sectree_height = struct.unpack_from("<I", data, 4)[0]
    offset = 8
    blocks: list[dict] = []
    block_index = 0

    while offset < len(data) and block_index < block_limit:
        block_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        payload = data[offset:offset + block_size]
        offset += block_size
        try:
            raw = lzo.decompress(payload, False, RAW_BYTES_PER_SECTREE)
            decompressed_size = len(raw)
            size_matches = decompressed_size == RAW_BYTES_PER_SECTREE
            first_dwords = [
                f"0x{value:08X}"
                for value in struct.unpack_from("<8I", raw, 0)
            ]
            error_message = None
        except lzo.error as exc:
            raw = b""
            decompressed_size = 0
            size_matches = False
            first_dwords = []
            error_message = str(exc)
        blocks.append(
            {
                "block_index": block_index,
                "compressed_size": block_size,
                "decompressed_size": decompressed_size,
                "decompressed_size_matches": size_matches,
                "first_dwords": first_dwords,
                "error": error_message,
            }
        )
        block_index += 1

    return {
        "lzo_backend_available": True,
        "sectree_width": sectree_width,
        "sectree_height": sectree_height,
        "validated_block_count": len(blocks),
        "expected_raw_block_size": RAW_BYTES_PER_SECTREE,
        "blocks": blocks,
    }


def build_attr_analysis_report(
    map_source: MapSource,
    server_attr_sample_path: str | Path | None = None,
) -> dict:
    attr_tiles = [parse_attr_file(path) for path in map_source.attr_files]
    geometry = geometry_from_setting(map_source.setting)
    attr_value_counter: Counter[int] = Counter()
    for attr_tile in attr_tiles:
        attr_value_counter.update(attr_tile.payload)
    unique_values = sorted(
        {
            value
            for attr_tile in attr_tiles
            for value in attr_tile.unique_values
        }
    )
    expected_attr_tile_count = map_source.setting.width * map_source.setting.height
    area_grid_matches_setting = (
        map_source.area_grid_width == map_source.setting.width
        and map_source.area_grid_height == map_source.setting.height
    )
    attr_layout_consistent = (
        len(attr_tiles) == expected_attr_tile_count and area_grid_matches_setting
    )

    server_cells_per_attr_tile_axis: float | None = None
    sectree_blocks_per_attr_tile: float | None = None
    if attr_layout_consistent:
        total_server_cells_x = geometry.sectree_width * geometry.cells_per_sectree_axis
        total_attr_cells_x = map_source.area_grid_width * 256
        server_cells_per_attr_tile_axis = round(total_server_cells_x / total_attr_cells_x, 3)
        sectree_blocks_per_attr_tile = round(
            (geometry.sectree_width * geometry.sectree_height) / len(attr_tiles),
            3,
        ) if attr_tiles else None

    report = {
        "map_name": map_source.name,
        "source_path": str(map_source.path),
        "setting_path": str(map_source.setting_path),
        "map_size": list(map_source.setting.map_size),
        "area_grid": {
            "width": map_source.area_grid_width,
            "height": map_source.area_grid_height,
            "matches_setting": area_grid_matches_setting,
        },
        "geometry": {
            "pixel_width": geometry.pixel_width,
            "pixel_height": geometry.pixel_height,
            "sectree_width": geometry.sectree_width,
            "sectree_height": geometry.sectree_height,
            "cells_per_sectree_axis": geometry.cells_per_sectree_axis,
            "dword_count_per_sectree": geometry.dword_count_per_sectree,
            "server_cells_per_attr_cell_axis": server_cells_per_attr_tile_axis,
            "sectree_blocks_per_attr_tile": sectree_blocks_per_attr_tile,
        },
        "area_directory_count": len(map_source.area_directories),
        "attr_file_count": len(attr_tiles),
        "expected_attr_tile_count": expected_attr_tile_count,
        "attr_layout_consistent": attr_layout_consistent,
        "attr_tile_size": 256,
        "attr_payload_size": 65536,
        "attr_unique_values": unique_values,
        "attr_value_totals": dict(sorted(attr_value_counter.items())),
        "attr_tiles": [
            {
                "path": str(attr_tile.path),
                "header_hex": attr_tile.header.hex(),
                "most_common_values": attr_tile.most_common_values,
            }
            for attr_tile in attr_tiles[:8]
        ],
        "warnings": list(map_source.warnings),
    }

    if server_attr_sample_path is not None:
        sample = analyze_server_attr_file(server_attr_sample_path)
        lzo_validation = validate_server_attr_lzo_blocks(server_attr_sample_path)
        report["server_attr_sample"] = {
            "path": str(sample.path),
            "size": sample.size,
            "sectree_width": sample.sectree_width,
            "sectree_height": sample.sectree_height,
            "block_count": sample.block_count,
            "first_block_sizes": sample.first_block_sizes,
            "block_size_stats": sample.block_size_stats,
            "lzo_validation": lzo_validation,
        }
        report["comparison"] = {
            "expected_attr_tile_count_from_setting": expected_attr_tile_count,
            "actual_attr_tile_count": len(attr_tiles),
            "expected_server_attr_sectree_count": (
                geometry.sectree_width * geometry.sectree_height
            ),
            "actual_server_attr_sectree_count": sample.block_count,
            "sectree_dimensions_match": (
                sample.sectree_width == geometry.sectree_width
                and sample.sectree_height == geometry.sectree_height
            ),
            "server_attr_sample_header_match": (
                sample.sectree_width == geometry.sectree_width
                and sample.sectree_height == geometry.sectree_height
            ),
            "lzo_backend_available": lzo_validation["lzo_backend_available"],
            "block_decompression_ready": all(
                block["decompressed_size_matches"]
                for block in lzo_validation["blocks"]
            ) if lzo_validation["lzo_backend_available"] else False,
        }

    return report


def build_batch_attr_summary(
    map_sources: list[MapSource],
    sample_root: str | Path,
) -> dict:
    sample_root_path = Path(sample_root)
    maps: list[dict] = []

    for map_source in map_sources:
        sample_path = find_matching_server_attr_sample(map_source.name, sample_root_path)
        if sample_path is None:
            continue

        report = build_attr_analysis_report(map_source, sample_path)
        maps.append(
            {
                "map_name": report["map_name"],
                "map_size": report["map_size"],
                "area_grid": report["area_grid"],
                "attr_layout_consistent": report["attr_layout_consistent"],
                "attr_unique_values": report["attr_unique_values"],
                "attr_value_totals": report["attr_value_totals"],
                "sectree_width": report["geometry"]["sectree_width"],
                "sectree_height": report["geometry"]["sectree_height"],
                "server_cells_per_attr_cell_axis": report["geometry"]["server_cells_per_attr_cell_axis"],
                "sectree_blocks_per_attr_tile": report["geometry"]["sectree_blocks_per_attr_tile"],
                "server_attr_size": report["server_attr_sample"]["size"],
                "server_attr_block_size_stats": report["server_attr_sample"]["block_size_stats"],
                "sectree_dimensions_match": report["comparison"]["sectree_dimensions_match"],
            }
        )

    return {
        "sample_root": str(sample_root_path),
        "map_count": len(maps),
        "maps": maps,
    }


def write_attr_analysis_report(
    map_source: MapSource,
    output_path: str | Path,
    server_attr_sample_path: str | Path | None = None,
) -> Path:
    report = build_attr_analysis_report(map_source, server_attr_sample_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return target


def write_batch_attr_summary(
    map_sources: list[MapSource],
    sample_root: str | Path,
    output_path: str | Path,
) -> Path:
    summary = build_batch_attr_summary(map_sources, sample_root)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return target


def find_matching_server_attr_sample(
    map_name: str,
    sample_root: str | Path,
) -> Path | None:
    sample_root_path = Path(sample_root)
    candidate_names = [map_name]
    if map_name.endswith("_pass"):
        base_name = map_name[:-5]
        if base_name:
            candidate_names.append(base_name)

    for candidate_name in candidate_names:
        candidate = sample_root_path / candidate_name / "server_attr"
        if candidate.exists():
            return candidate
    return None
