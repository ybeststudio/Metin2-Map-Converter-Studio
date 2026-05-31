from __future__ import annotations

from app.core.map_reader import discover_map_sources
from app.core.raw_sectree_block_packer import (
    RAW_BYTES_PER_SECTREE,
    build_batch_raw_sectree_block_summary,
    build_raw_sectree_block_report,
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


def test_build_raw_sectree_block_report_creates_expected_block_shape(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1]) + (b"\x00" * (65536 - 2))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_dir = tmp_path / "samples" / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    server_attr_sample = (
        (4).to_bytes(4, "little")
        + (4).to_bytes(4, "little")
        + ((0).to_bytes(4, "little") * 16)
    )
    (sample_dir / "server_attr").write_bytes(server_attr_sample)

    map_source = discover_map_sources(source_root)[0]
    report = build_raw_sectree_block_report(
        map_source,
        sample_block_limit=1,
        sample_dword_limit=4,
        sample_root=tmp_path / "samples",
    )

    assert report["total_block_count"] == 16
    assert report["raw_bytes_per_block"] == RAW_BYTES_PER_SECTREE
    assert report["total_raw_uncompressed_bytes"] == 16 * RAW_BYTES_PER_SECTREE
    assert report["sample_blocks"][0]["first_dwords"] == [
        "0x00000000",
        "0x00000000",
        "0x00000041",
        "0x00000041",
    ]
    assert report["server_attr_reference"]["block_count_matches"] is True


def test_build_batch_raw_sectree_block_summary_collects_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    for map_name, value in (("metin2_map_test_1", 0), ("metin2_map_test_2", 201)):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (bytes([value]) * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = build_batch_raw_sectree_block_summary(map_sources)

    assert summary["map_count"] == 2
    assert summary["total_raw_uncompressed_bytes"] == 2 * 16 * RAW_BYTES_PER_SECTREE
    assert summary["top_first_block_checksums"]
