from __future__ import annotations

import json
from pathlib import Path

from app.core.attr_family_analyzer import (
    build_attr_family_report,
    build_batch_attr_family_summary,
)
from app.core.map_reader import MapSource


def build_attr_dword_candidate_report(
    map_source: MapSource,
    batch_summary: dict | None = None,
) -> dict:
    family_report = build_attr_family_report(map_source)
    pair_groups = {item["pair_base"]: item for item in family_report["pair_groups"]}

    value_candidates = [
        _build_value_candidate(value_profile, pair_groups, family_report)
        for value_profile in family_report["value_profiles"]
    ]
    family_candidates = [
        _build_family_candidate(family_group)
        for family_group in family_report["family_groups"]
    ]

    report = {
        "map_name": map_source.name,
        "total_attr_cells": family_report["total_attr_cells"],
        "family_summary": {
            "top_families": family_report["family_groups"][:8],
            "top_pairs": family_report["pair_groups"][:8],
            "bit_usage": family_report["bit_usage"],
        },
        "candidate_rules": {
            "scope": "analysis_only",
            "export_ready": False,
            "notes": [
                "Bu rapor kesin DWORD bit maskesi yazmaz",
                "Aday roller yalnizca korelasyon ve bit yapisina gore uretilir",
                "Gercek server_attr export acilmadan once LZO ve DWORD esleme dogrulanmalidir",
            ],
        },
        "value_candidates": value_candidates,
        "family_candidates": family_candidates,
        "ambiguity_notes": _build_ambiguity_notes(family_report, value_candidates),
    }

    if batch_summary is not None:
        report["global_context"] = {
            "map_count": batch_summary["map_count"],
            "global_top_values": batch_summary["global_top_values"][:12],
            "global_top_families": batch_summary["global_top_families"][:8],
        }

    return report


def build_batch_attr_dword_candidate_summary(map_sources: list[MapSource]) -> dict:
    batch_family_summary = build_batch_attr_family_summary(map_sources)
    maps: list[dict] = []

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        report = build_attr_dword_candidate_report(map_source, batch_family_summary)
        maps.append(
            {
                "map_name": report["map_name"],
                "top_value_candidates": report["value_candidates"][:8],
                "top_family_candidates": report["family_candidates"][:6],
                "ambiguity_notes": report["ambiguity_notes"],
            }
        )

    return {
        "map_count": len(maps),
        "global_context": {
            "global_top_values": batch_family_summary["global_top_values"][:12],
            "global_top_families": batch_family_summary["global_top_families"][:8],
        },
        "maps": maps,
    }


def write_attr_dword_candidate_report(
    map_source: MapSource,
    output_path: str | Path,
    batch_summary: dict | None = None,
) -> Path:
    report = build_attr_dword_candidate_report(map_source, batch_summary)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def write_batch_attr_dword_candidate_summary(
    map_sources: list[MapSource],
    output_path: str | Path,
) -> Path:
    summary = build_batch_attr_dword_candidate_summary(map_sources)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def _build_value_candidate(value_profile: dict, pair_groups: dict[int, dict], family_report: dict) -> dict:
    value = value_profile["value"]
    family_base = value_profile["family_base"]
    pair_group = pair_groups.get(value_profile["pair_base"])
    roles: list[dict] = []

    if value == 0:
        roles.append(_role("zero_state_candidate", "high", "Deger sifir ve hic bit set degil"))
        roles.append(_role("walkable_candidate", "low", "Sifir durum cogu sistemde temiz taban durum olabilir"))

    if pair_group and pair_group["bit0_toggle_candidate"]:
        if value % 2 == 0:
            roles.append(
                _role(
                    "base_state_candidate",
                    "high",
                    f"{value} degeri ayni pair icinde bit0 kapali temel durum gibi gorunuyor",
                )
            )
        else:
            roles.append(
                _role(
                    "toggled_state_candidate",
                    "high",
                    f"{value} degeri ayni pair icinde bit0 acik alternatif durum gibi gorunuyor",
                )
            )

    if family_base == 0:
        roles.append(
            _role(
                "core_terrain_candidate",
                "medium",
                "Dusuk-bit temel aile icinde yer aliyor",
            )
        )
        if value in {1, 3, 5, 7}:
            roles.append(
                _role(
                    "blocked_or_restricted_candidate",
                    "low",
                    "Bit0 aktif ve temel aile icinde; engel veya kisit togglesi olabilir",
                )
            )
        if value in {2, 3}:
            roles.append(
                _role(
                    "water_or_slope_candidate",
                    "low",
                    "Bit1 aktif; ikincil cevresel durum adayi",
                )
            )
        if value in {4, 5, 6, 7}:
            roles.append(
                _role(
                    "special_surface_modifier_candidate",
                    "low",
                    "Bit2 aktif; nadir yuzey degistirici adayi",
                )
            )

    if family_base in {8, 16, 48}:
        roles.append(
            _role(
                "extended_surface_candidate",
                "medium",
                "Dusuk-bit tabanin genisletilmis aile varyanti gibi gorunuyor",
            )
        )

    if 0x40 <= family_base < 0x80:
        roles.append(
            _role(
                "special_zone_candidate",
                "medium",
                "0x40-0x7F arasi aile; arena, event veya ozel bolge overlayi olabilir",
            )
        )

    if family_base >= 0xC0:
        roles.append(
            _role(
                "high_overlay_candidate",
                "medium",
                "Yuksek-bit aile; ana zemin uzerine eklenen ozel durum katmani olabilir",
            )
        )
        if value % 2 == 0:
            roles.append(
                _role(
                    "overlay_base_candidate",
                    "medium",
                    "Yuksek-bit aile icinde even taban varyant",
                )
            )
        else:
            roles.append(
                _role(
                    "overlay_toggled_candidate",
                    "medium",
                    "Yuksek-bit aile icinde odd toggled varyant",
                )
            )

    return {
        "value": value,
        "hex": value_profile["hex"],
        "share": value_profile["share"],
        "family_base": family_base,
        "pair_base": value_profile["pair_base"],
        "roles": roles,
    }


def _build_family_candidate(family_group: dict) -> dict:
    family_base = family_group["family_base"]
    roles: list[dict] = []

    if family_base == 0:
        roles.append(_role("core_terrain_family", "high", "Global olarak baskin temel aile"))
        roles.append(_role("walk_block_state_family", "medium", "Bit0/bit1/bit2 ile temel durumlar tasiyor gibi gorunuyor"))
    elif family_base < 0x40:
        roles.append(_role("extended_terrain_family", "medium", "Temel ailenin genislemis varyanti olabilir"))
    elif family_base < 0x80:
        roles.append(_role("special_zone_family", "medium", "Orta-seviye ozel bolge veya arena/event ailesi olabilir"))
    elif family_base < 0xC0:
        roles.append(_role("high_mid_overlay_family", "low", "Yuksek-orta overlay ailesi adayi"))
    else:
        roles.append(_role("high_overlay_family", "high", "Yuksek-bit overlay veya ozel katman ailesi adayi"))

    return {
        "family_base": family_base,
        "family_hex": family_group["family_hex"],
        "share": family_group["share"],
        "values": family_group["values"],
        "roles": roles,
    }


def _build_ambiguity_notes(family_report: dict, value_candidates: list[dict]) -> list[str]:
    notes = list(family_report["candidate_notes"])
    notes.append("Walkable ve blocked ayrimi henuz kesin degil; sadece aday rol veriliyor")
    notes.append("DWORD bit maskeleri henuz uretilmiyor; bu rapor export icin tek basina kullanilmaz")

    if any(candidate["family_base"] >= 0xC0 for candidate in value_candidates):
        notes.append("Yuksek-bit aileler mevcut; bunlarin taban mi overlay mi oldugu server DWORD tarafinda dogrulanmali")

    if any(candidate["pair_base"] == 0 for candidate in value_candidates):
        notes.append("0/1 taban ciftleri bulundu; bu cift icin walkable-blocked yonu henuz acik degil")

    return notes


def _role(name: str, confidence: str, reason: str) -> dict:
    return {
        "name": name,
        "confidence": confidence,
        "reason": reason,
    }
