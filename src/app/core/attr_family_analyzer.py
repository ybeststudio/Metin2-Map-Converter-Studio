from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from app.core.attr_parser import parse_attr_file
from app.core.map_reader import MapSource


def build_attr_value_counter(map_source: MapSource) -> Counter[int]:
    counter: Counter[int] = Counter()
    for attr_file in map_source.attr_files:
        counter.update(parse_attr_file(attr_file).payload)
    return counter


def build_attr_family_report(map_source: MapSource) -> dict:
    value_counter = build_attr_value_counter(map_source)
    total_cells = sum(value_counter.values())
    family_counter: Counter[int] = Counter()
    pair_counter: Counter[int] = Counter()
    family_to_values: dict[int, set[int]] = defaultdict(set)
    pair_to_values: dict[int, set[int]] = defaultdict(set)

    for value, count in value_counter.items():
        family_base = value & 0xF8
        pair_base = value & 0xFE
        family_counter[family_base] += count
        pair_counter[pair_base] += count
        family_to_values[family_base].add(value)
        pair_to_values[pair_base].add(value)

    report = {
        "map_name": map_source.name,
        "attr_file_count": len(map_source.attr_files),
        "total_attr_cells": total_cells,
        "unique_value_count": len(value_counter),
        "value_profiles": _build_value_profiles(value_counter, total_cells),
        "pair_groups": _build_pair_groups(pair_counter, pair_to_values, total_cells),
        "family_groups": _build_family_groups(family_counter, family_to_values, total_cells),
        "bit_usage": _build_bit_usage(value_counter, total_cells),
        "candidate_notes": _build_candidate_notes(value_counter, family_counter, total_cells),
    }
    return report


def build_batch_attr_family_summary(map_sources: list[MapSource]) -> dict:
    maps: list[dict] = []
    aggregate_values: Counter[int] = Counter()
    aggregate_families: Counter[int] = Counter()

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        report = build_attr_family_report(map_source)
        maps.append(
            {
                "map_name": report["map_name"],
                "attr_file_count": report["attr_file_count"],
                "total_attr_cells": report["total_attr_cells"],
                "unique_value_count": report["unique_value_count"],
                "top_values": report["value_profiles"][:8],
                "top_families": report["family_groups"][:6],
                "candidate_notes": report["candidate_notes"],
            }
        )
        for item in report["value_profiles"]:
            aggregate_values[item["value"]] += item["count"]
        for item in report["family_groups"]:
            aggregate_families[item["family_base"]] += item["count"]

    total_cells = sum(aggregate_values.values())
    return {
        "map_count": len(maps),
        "total_attr_cells": total_cells,
        "global_top_values": _build_value_profiles(aggregate_values, total_cells)[:20],
        "global_top_families": _build_family_groups(
            aggregate_families,
            _family_values_from_counter(aggregate_values),
            total_cells,
        )[:20],
        "maps": maps,
    }


def write_attr_family_report(map_source: MapSource, output_path: str | Path) -> Path:
    report = build_attr_family_report(map_source)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def write_batch_attr_family_summary(
    map_sources: list[MapSource],
    output_path: str | Path,
) -> Path:
    summary = build_batch_attr_family_summary(map_sources)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def _build_value_profiles(value_counter: Counter[int], total_cells: int) -> list[dict]:
    profiles: list[dict] = []
    for value, count in value_counter.most_common():
        profiles.append(
            {
                "value": value,
                "hex": f"0x{value:02X}",
                "count": count,
                "share": _ratio(count, total_cells),
                "bits_set": [bit for bit in range(8) if value & (1 << bit)],
                "bit_count": int(value).bit_count(),
                "family_base": value & 0xF8,
                "pair_base": value & 0xFE,
            }
        )
    return profiles


def _build_pair_groups(
    pair_counter: Counter[int],
    pair_to_values: dict[int, set[int]],
    total_cells: int,
) -> list[dict]:
    groups: list[dict] = []
    for pair_base, count in pair_counter.most_common():
        values = sorted(pair_to_values[pair_base])
        groups.append(
            {
                "pair_base": pair_base,
                "values": values,
                "count": count,
                "share": _ratio(count, total_cells),
                "bit0_toggle_candidate": len(values) >= 2 and any(
                    (value ^ 1) in values for value in values
                ),
            }
        )
    return groups


def _build_family_groups(
    family_counter: Counter[int],
    family_to_values: dict[int, set[int]],
    total_cells: int,
) -> list[dict]:
    groups: list[dict] = []
    for family_base, count in family_counter.most_common():
        values = sorted(family_to_values[family_base])
        groups.append(
            {
                "family_base": family_base,
                "family_hex": f"0x{family_base:02X}",
                "values": values,
                "count": count,
                "share": _ratio(count, total_cells),
                "candidate_interpretation": _family_interpretation(family_base),
            }
        )
    return groups


def _build_bit_usage(value_counter: Counter[int], total_cells: int) -> list[dict]:
    usage: list[dict] = []
    for bit in range(8):
        set_count = sum(count for value, count in value_counter.items() if value & (1 << bit))
        usage.append(
            {
                "bit": bit,
                "set_count": set_count,
                "set_ratio": _ratio(set_count, total_cells),
            }
        )
    return usage


def _build_candidate_notes(
    value_counter: Counter[int],
    family_counter: Counter[int],
    total_cells: int,
) -> list[str]:
    notes: list[str] = []
    if not total_cells:
        return ["Attr verisi bulunamadi"]

    if any(((value ^ 1) in value_counter) for value in value_counter):
        notes.append("Bit0 birincil durum degistirici adayi olabilir; eslenmis ciftler bulundu")

    odd_count = sum(count for value, count in value_counter.items() if value & 1)
    odd_ratio = _ratio(odd_count, total_cells)
    if 0.1 < odd_ratio < 0.9:
        notes.append(
            f"Bit0 birincil durum degistirici adayi olabilir; set orani {odd_ratio:.3f}"
        )

    if any(family >= 0xC0 for family in family_counter):
        notes.append("0xC0 ve ustu aileler bulundu; yuksek-bit overlay adayi olabilir")

    if any(0x40 <= family < 0x80 for family in family_counter):
        notes.append("0x40-0x7F arasi aileler bulundu; orta-seviye flag ailesi adayi olabilir")

    dominant_families = [
        family for family, count in family_counter.most_common(3) if _ratio(count, total_cells) >= 0.1
    ]
    if dominant_families:
        notes.append(
            "Baskin aileler: "
            + ", ".join(f"0x{family:02X}" for family in dominant_families)
        )

    return notes


def _family_values_from_counter(value_counter: Counter[int]) -> dict[int, set[int]]:
    family_to_values: dict[int, set[int]] = defaultdict(set)
    for value in value_counter:
        family_to_values[value & 0xF8].add(value)
    return family_to_values


def _family_interpretation(family_base: int) -> str:
    if family_base < 0x08:
        return "dusuk-bit temel aile adayi"
    if family_base < 0x40:
        return "genisletilmis dusuk-bit aile adayi"
    if family_base < 0x80:
        return "orta-seviye flag ailesi adayi"
    if family_base < 0xC0:
        return "yuksek-orta flag ailesi adayi"
    return "yuksek-bit overlay ailesi adayi"


def _ratio(left: int, right: int) -> float:
    if right == 0:
        return 0.0
    return round(left / right, 6)
