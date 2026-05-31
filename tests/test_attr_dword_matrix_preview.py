from __future__ import annotations

from app.core.attr_dword_matrix_preview import (
    build_attr_dword_matrix_preview,
    build_batch_attr_dword_matrix_preview_summary,
    map_attr_value_to_candidate_dword,
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


def test_map_attr_value_to_candidate_dword_maps_expected_bits() -> None:
    assert map_attr_value_to_candidate_dword(0) == 0
    assert map_attr_value_to_candidate_dword(1) == ((1 << 0) | (1 << 6))
    assert map_attr_value_to_candidate_dword(3) == ((1 << 0) | (1 << 1) | (1 << 6))
    assert map_attr_value_to_candidate_dword(201) == ((1 << 0) | (1 << 5) | (1 << 6))


def test_build_attr_dword_matrix_preview_generates_scaled_preview(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1]) + (b"\x00" * (65536 - 2))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    report = build_attr_dword_matrix_preview(map_source, preview_width=4, preview_height=2)

    assert report["scale_factor"] == 2
    assert report["server_grid"]["width"] == 512
    assert report["server_grid"]["height"] == 512
    assert report["preview_window"]["rows"][0][:4] == [
        "00000000",
        "00000000",
        "00000041",
        "00000041",
    ]


def test_build_batch_attr_dword_matrix_preview_summary_collects_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    for map_name, value in (("metin2_map_test_1", 0), ("metin2_map_test_2", 201)):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (bytes([value]) * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_attr_dword_matrix_preview_summary(map_sources)

    assert summary["map_count"] == 2
    assert "high_overlay_candidate" in summary["aggregate_candidate_bits"]
