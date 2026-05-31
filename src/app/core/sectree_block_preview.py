from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.core.attr_dword_matrix_preview import map_attr_value_to_candidate_dword
from app.core.coordinate import geometry_from_setting
from app.core.map_reader import MapSource
from app.core.attr_parser import parse_attr_file


def build_sectree_block_preview(
    map_source: MapSource,
    sample_block_limit: int = 8,
    sample_rows: int = 4,
    sample_cols: int = 8,
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
            _build_single_block_summary(
                attr_tiles,
                block_x,
                block_y,
                geometry.sectree_width,
                scale,
                sample_rows,
                sample_cols,
            )
        )

    return {
        "map_name": map_source.name,
        "sectree_grid": {
            "width": geometry.sectree_width,
            "height": geometry.sectree_height,
        },
        "server_cells_per_sectree_axis": geometry.cells_per_sectree_axis,
        "dword_count_per_sectree": geometry.dword_count_per_sectree,
        "scale_factor": scale,
        "total_block_count": total_block_count,
        "sampling_mode": "row_major_first_n_blocks",
        "sample_block_limit": min(sample_block_limit, total_block_count),
        "sample_blocks": sample_blocks,
    }


def build_batch_sectree_block_preview_summary(map_sources: list[MapSource]) -> dict:
    maps: list[dict] = []
    first_block_dwords: Counter[int] = Counter()

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        try:
            report = build_sectree_block_preview(map_source, sample_block_limit=1)
        except ValueError:
            continue

        first_block = report["sample_blocks"][0] if report["sample_blocks"] else None
        if first_block:
            first_block_dwords[first_block["dominant_dword"]] += 1

        maps.append(
            {
                "map_name": report["map_name"],
                "scale_factor": report["scale_factor"],
                "total_block_count": report["total_block_count"],
                "dword_count_per_sectree": report["dword_count_per_sectree"],
                "first_block": first_block,
            }
        )

    return {
        "map_count": len(maps),
        "sampling_mode": "first_block_only_for_batch_summary",
        "dominant_first_block_dwords": [
            {
                "dword": dword,
                "hex": f"0x{dword:08X}",
                "map_count": count,
            }
            for dword, count in first_block_dwords.most_common()
        ],
        "maps": maps,
    }


def write_sectree_block_preview(
    map_source: MapSource,
    output_path: str | Path,
    sample_block_limit: int = 8,
    sample_rows: int = 4,
    sample_cols: int = 8,
) -> Path:
    report = build_sectree_block_preview(
        map_source,
        sample_block_limit=sample_block_limit,
        sample_rows=sample_rows,
        sample_cols=sample_cols,
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def write_batch_sectree_block_preview_summary(
    map_sources: list[MapSource],
    output_path: str | Path,
) -> Path:
    summary = build_batch_sectree_block_preview_summary(map_sources)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def _build_single_block_summary(
    attr_tiles: dict[tuple[int, int], bytes],
    block_x: int,
    block_y: int,
    sectree_width: int,
    scale: int,
    sample_rows: int,
    sample_cols: int,
) -> dict:
    dword_counter: Counter[int] = Counter()
    nonzero_count = 0
    rows: list[list[str]] = []

    base_x = block_x * 128
    base_y = block_y * 128

    for local_y in range(128):
        row_preview: list[str] = []
        for local_x in range(128):
            server_x = base_x + local_x
            server_y = base_y + local_y
            attr_x = server_x // scale
            attr_y = server_y // scale
            attr_value = _get_attr_value(attr_tiles, attr_x, attr_y)
            dword = map_attr_value_to_candidate_dword(attr_value)
            dword_counter[dword] += 1
            if dword != 0:
                nonzero_count += 1
            if local_y < sample_rows and local_x < sample_cols:
                row_preview.append(f"{dword:08X}")
        if local_y < sample_rows:
            rows.append(row_preview)

    dominant_dword, dominant_count = dword_counter.most_common(1)[0]
    return {
        "block_index": block_y * sectree_width + block_x,
        "block_x": block_x,
        "block_y": block_y,
        "dominant_dword": dominant_dword,
        "dominant_hex": f"0x{dominant_dword:08X}",
        "dominant_share": _ratio(dominant_count, 128 * 128),
        "nonzero_ratio": _ratio(nonzero_count, 128 * 128),
        "unique_dword_count": len(dword_counter),
        "top_dwords": [
            {
                "dword": dword,
                "hex": f"0x{dword:08X}",
                "count": count,
                "share": _ratio(count, 128 * 128),
            }
            for dword, count in dword_counter.most_common(8)
        ],
        "preview_rows": rows,
    }


def _load_attr_tiles(map_source: MapSource) -> dict[tuple[int, int], bytes]:
    tiles: dict[tuple[int, int], bytes] = {}
    for attr_file in map_source.attr_files:
        parsed = parse_attr_file(attr_file)
        coord = (int(attr_file.parent.name[:3]), int(attr_file.parent.name[3:]))
        tiles[coord] = parsed.payload
    return tiles


def _resolve_scale(map_source: MapSource, geometry) -> int:
    attr_width = map_source.area_grid_width * 256
    attr_height = map_source.area_grid_height * 256
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
