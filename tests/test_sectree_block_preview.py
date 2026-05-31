from __future__ import annotations

from app.core.map_reader import discover_map_sources
from app.core.sectree_block_preview import (
    build_batch_sectree_block_preview_summary,
    build_sectree_block_preview,
)


VALID_SETTING = """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

ViewRadius 128

MapSize 1 1
BasePosition 0 0
TextureSet textureset\\test.txt
Environment test.msenv
"""


def test_build_sectree_block_preview_generates_first_block_summary(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1]) + (b"\x00" * (65536 - 2))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    report = build_sectree_block_preview(
        map_source,
        sample_block_limit=1,
        sample_rows=2,
        sample_cols=4,
    )

    assert report["total_block_count"] == 16
    assert report["dword_count_per_sectree"] == 16384
    first_block = report["sample_blocks"][0]
    assert first_block["block_index"] == 0
    assert first_block["preview_rows"][0] == [
        "00000000",
        "00000000",
        "00000041",
        "00000041",
    ]


def test_build_batch_sectree_block_preview_summary_collects_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    for map_name, value in (("metin2_map_test_1", 0), ("metin2_map_test_2", 201)):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (bytes([value]) * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_sectree_block_preview_summary(map_sources)

    assert summary["map_count"] == 2
    assert summary["maps"][0]["first_block"] is not None
    assert summary["dominant_first_block_dwords"]
