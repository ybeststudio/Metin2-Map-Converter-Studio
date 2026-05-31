from __future__ import annotations

import json

from app.core.map_reader import discover_map_sources
from app.core.server_attr_analyzer import build_batch_attr_summary


VALID_SETTING = """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

ViewRadius 128

MapSize 1 1
BasePosition 0 0
TextureSet textureset\\test.txt
Environment test.msenv
"""


def test_build_batch_attr_summary_collects_matching_samples(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_dir = tmp_path / "samples" / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    server_attr_sample = (
        (4).to_bytes(4, "little")
        + (4).to_bytes(4, "little")
        + ((0).to_bytes(4, "little") * 16)
    )
    (sample_dir / "server_attr").write_bytes(server_attr_sample)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_attr_summary(map_sources, tmp_path / "samples")

    assert summary["map_count"] == 1
    assert summary["maps"][0]["map_name"] == "metin2_map_test"
    assert summary["maps"][0]["attr_layout_consistent"] is True
    assert summary["maps"][0]["sectree_dimensions_match"] is True
    assert summary["maps"][0]["server_cells_per_attr_cell_axis"] == 2.0
