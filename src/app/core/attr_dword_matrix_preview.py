from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.core.attr_parser import parse_attr_file
from app.core.coordinate import geometry_from_setting
from app.core.map_reader import MapSource


CANDIDATE_DWORD_BITS = {
    0: "pair_toggle_bit0_candidate",
    1: "secondary_env_bit1_candidate",
    2: "surface_modifier_bit2_candidate",
    3: "extended_family_candidate",
    4: "special_zone_candidate",
    5: "high_overlay_candidate",
    6: "nonzero_value_candidate",
}


def build_attr_dword_matrix_preview(
    map_source: MapSource,
    preview_width: int = 16,
    preview_height: int = 16,
) -> dict:
    geometry = geometry_from_setting(map_source.setting)
    attr_width = map_source.area_grid_width * 256
    attr_height = map_source.area_grid_height * 256
    if attr_width == 0 or attr_height == 0:
        raise ValueError(f"Attr grid olusturulamadi: {map_source.name}")

    server_width = geometry.sectree_width * geometry.cells_per_sectree_axis
    server_height = geometry.sectree_height * geometry.cells_per_sectree_axis
    scale_x = server_width // attr_width if attr_width else 0
    scale_y = server_height // attr_height if attr_height else 0
    if scale_x <= 0 or scale_y <= 0 or scale_x != scale_y:
        raise ValueError(
            f"Tutarsiz attr->server olcegi: {map_source.name} ({scale_x}, {scale_y})"
        )

    scale = scale_x
    attr_counter = _build_attr_value_counter(map_source)
    dword_counter: Counter[int] = Counter()
    candidate_bit_cell_counts: Counter[int] = Counter()

    for value, count in attr_counter.items():
        dword_value = map_attr_value_to_candidate_dword(value)
        expanded_count = count * scale * scale
        dword_counter[dword_value] += expanded_count
        for bit in CANDIDATE_DWORD_BITS:
            if dword_value & (1 << bit):
                candidate_bit_cell_counts[bit] += expanded_count

    preview_rows = _build_preview_rows(
        map_source,
        width=min(preview_width, server_width),
        height=min(preview_height, server_height),
        scale=scale,
    )

    return {
        "map_name": map_source.name,
        "server_grid": {
            "width": server_width,
            "height": server_height,
        },
        "attr_grid": {
            "width": attr_width,
            "height": attr_height,
        },
        "scale_factor": scale,
        "candidate_dword_bits": {
            str(bit): label for bit, label in CANDIDATE_DWORD_BITS.items()
        },
        "global_dword_profiles": [
            {
                "dword": dword_value,
                "hex": f"0x{dword_value:08X}",
                "count": count,
                "share": _ratio(count, server_width * server_height),
            }
            for dword_value, count in dword_counter.most_common()
        ],
        "candidate_bit_cell_counts": {
            CANDIDATE_DWORD_BITS[bit]: {
                "count": count,
                "share": _ratio(count, server_width * server_height),
            }
            for bit, count in sorted(candidate_bit_cell_counts.items())
        },
        "preview_window": {
            "width": min(preview_width, server_width),
            "height": min(preview_height, server_height),
            "rows": preview_rows,
        },
    }


def build_batch_attr_dword_matrix_preview_summary(map_sources: list[MapSource]) -> dict:
    maps: list[dict] = []
    aggregate_bits: Counter[int] = Counter()

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        try:
            report = build_attr_dword_matrix_preview(map_source, preview_width=8, preview_height=8)
        except ValueError:
            continue
        maps.append(
            {
                "map_name": report["map_name"],
                "scale_factor": report["scale_factor"],
                "top_dwords": report["global_dword_profiles"][:8],
                "candidate_bit_cell_counts": report["candidate_bit_cell_counts"],
            }
        )
        for bit_name, item in report["candidate_bit_cell_counts"].items():
            bit_index = _bit_name_to_index(bit_name)
            aggregate_bits[bit_index] += item["count"]

    total = sum(aggregate_bits.values())
    return {
        "map_count": len(maps),
        "aggregate_candidate_bits": {
            CANDIDATE_DWORD_BITS[bit]: {
                "count": count,
                "share": _ratio(count, total),
            }
            for bit, count in sorted(aggregate_bits.items())
        },
        "maps": maps,
    }


def write_attr_dword_matrix_preview(
    map_source: MapSource,
    output_path: str | Path,
    preview_width: int = 16,
    preview_height: int = 16,
) -> Path:
    report = build_attr_dword_matrix_preview(map_source, preview_width, preview_height)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def write_batch_attr_dword_matrix_preview_summary(
    map_sources: list[MapSource],
    output_path: str | Path,
) -> Path:
    summary = build_batch_attr_dword_matrix_preview_summary(map_sources)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def map_attr_value_to_candidate_dword(value: int) -> int:
    dword = 0
    family_base = value & 0xF8

    if value & 0x01:
        dword |= 1 << 0
    if value & 0x02:
        dword |= 1 << 1
    if value & 0x04:
        dword |= 1 << 2
    if 0x08 <= family_base < 0x40:
        dword |= 1 << 3
    if 0x40 <= family_base < 0x80:
        dword |= 1 << 4
    if family_base >= 0xC0:
        dword |= 1 << 5
    if value != 0:
        dword |= 1 << 6

    return dword


def _build_attr_value_counter(map_source: MapSource) -> Counter[int]:
    counter: Counter[int] = Counter()
    for attr_file in map_source.attr_files:
        counter.update(parse_attr_file(attr_file).payload)
    return counter


def _build_preview_rows(
    map_source: MapSource,
    width: int,
    height: int,
    scale: int,
) -> list[list[str]]:
    attr_tiles = {
        (int(path.parent.name[:3]), int(path.parent.name[3:])): parse_attr_file(path)
        for path in map_source.attr_files
    }
    rows: list[list[str]] = []

    for server_y in range(height):
        row: list[str] = []
        attr_y = server_y // scale
        for server_x in range(width):
            attr_x = server_x // scale
            value = _get_attr_value(attr_tiles, attr_x, attr_y)
            dword = map_attr_value_to_candidate_dword(value)
            row.append(f"{dword:08X}")
        rows.append(row)

    return rows


def _get_attr_value(attr_tiles: dict[tuple[int, int], object], attr_x: int, attr_y: int) -> int:
    tile_x = attr_x // 256
    tile_y = attr_y // 256
    local_x = attr_x % 256
    local_y = attr_y % 256
    tile = attr_tiles.get((tile_x, tile_y))
    if tile is None:
        return 0
    offset = local_y * 256 + local_x
    return tile.payload[offset]


def _bit_name_to_index(name: str) -> int:
    for bit, label in CANDIDATE_DWORD_BITS.items():
        if label == name:
            return bit
    raise KeyError(name)


def _ratio(left: int, right: int) -> float:
    if right == 0:
        return 0.0
    return round(left / right, 6)
