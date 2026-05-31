from __future__ import annotations

from app.core.attr_dword_candidate_mapper import (
    build_attr_dword_candidate_report,
    build_batch_attr_dword_candidate_summary,
)
from app.core.attr_family_analyzer import build_batch_attr_family_summary
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


def test_build_attr_dword_candidate_report_assigns_expected_roles(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1, 200, 201]) + (b"\x00" * (65536 - 4))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    batch_summary = build_batch_attr_family_summary([map_source])
    report = build_attr_dword_candidate_report(map_source, batch_summary)

    value_map = {item["value"]: item for item in report["value_candidates"]}
    zero_roles = {role["name"] for role in value_map[0]["roles"]}
    one_roles = {role["name"] for role in value_map[1]["roles"]}
    high_roles = {role["name"] for role in value_map[201]["roles"]}

    assert "zero_state_candidate" in zero_roles
    assert "walkable_candidate" in zero_roles
    assert "toggled_state_candidate" in one_roles
    assert "high_overlay_candidate" in high_roles
    assert any("Walkable ve blocked ayrimi" in note for note in report["ambiguity_notes"])


def test_build_batch_attr_dword_candidate_summary_collects_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    for map_name, values in (
        ("metin2_map_test_1", bytes([0, 1])),
        ("metin2_map_test_2", bytes([200, 201])),
    ):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        payload = values + (values[:1] * (65536 - len(values)))
        attr_data = bytes.fromhex("4a0a00010001") + payload
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_attr_dword_candidate_summary(map_sources)

    assert summary["map_count"] == 2
    assert len(summary["global_context"]["global_top_families"]) >= 1
    assert summary["maps"][0]["top_value_candidates"]
