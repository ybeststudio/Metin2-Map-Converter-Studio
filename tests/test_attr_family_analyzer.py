from __future__ import annotations

from app.core.attr_family_analyzer import (
    build_attr_family_report,
    build_batch_attr_family_summary,
)
from app.core.map_reader import discover_map_sources


VALID_SETTING = """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

ViewRadius 128

MapSize 1 1
BasePosition 0 0
TextureSet textureset\\test.txt
Environment test.msenv
"""


def test_build_attr_family_report_groups_values_by_family_and_pair(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1, 4, 5, 200, 201]) + (b"\x00" * (65536 - 6))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    report = build_attr_family_report(map_source)

    assert report["map_name"] == "metin2_map_test"
    assert report["unique_value_count"] == 6
    assert report["value_profiles"][0]["value"] == 0
    assert report["pair_groups"][0]["bit0_toggle_candidate"] is True
    family_bases = {item["family_base"] for item in report["family_groups"]}
    assert 0 in family_bases
    assert 200 in family_bases
    assert any("Bit0" in note for note in report["candidate_notes"])


def test_build_batch_attr_family_summary_aggregates_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    for map_name, value in (("metin2_map_test_1", 1), ("metin2_map_test_2", 201)):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (bytes([value]) * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_attr_family_summary(map_sources)

    assert summary["map_count"] == 2
    assert summary["global_top_values"][0]["value"] in {1, 201}
    assert len(summary["global_top_families"]) >= 2
