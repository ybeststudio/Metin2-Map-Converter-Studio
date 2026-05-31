from __future__ import annotations

from app.core.map_reader import discover_map_sources
from app.core.server_attr_block_diff import (
    build_batch_server_attr_block_diff_summary,
    build_server_attr_block_diff_report,
)
from app.core.server_attr_exporter import export_server_attr


VALID_SETTING = """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

ViewRadius 128

MapSize 1 1
BasePosition 0 0
TextureSet textureset\\test.txt
Environment test.msenv
"""


def test_build_server_attr_block_diff_report_compares_first_blocks(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_root = tmp_path / "samples" / "metin2_map_test"
    sample_root.mkdir(parents=True)

    map_source = discover_map_sources(source_root)[0]
    export_server_attr(
        map_source,
        sample_root / "server_attr",
        mapping_profile="exe_compat_v2",
    )

    report = build_server_attr_block_diff_report(
        map_source,
        sample_root=tmp_path / "samples",
        mapping_profile="exe_compat_v2",
        block_limit=2,
    )

    assert report["validated_block_count"] == 2
    assert report["compared_blocks"][0]["mismatch_count"] == 0
    assert report["compared_blocks"][0]["generated_first_dwords"] == [
        "0x00000001",
        "0x00000001",
        "0x00000001",
        "0x00000001",
        "0x00000001",
        "0x00000001",
        "0x00000001",
        "0x00000001",
    ]


def test_build_batch_server_attr_block_diff_summary_collects_matching_maps(tmp_path) -> None:
    source_root = tmp_path / "client"

    for map_name, fill_value in (
        ("metin2_map_test_a", b"\x01"),
        ("metin2_map_test_b", b"\x02"),
    ):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (fill_value * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

        sample_dir = tmp_path / "samples" / map_name
        sample_dir.mkdir(parents=True)

    map_sources = discover_map_sources(source_root)
    for map_source in map_sources:
        export_server_attr(
            map_source,
            tmp_path / "samples" / map_source.name / "server_attr",
            mapping_profile="exe_compat_v2",
        )

    summary = build_batch_server_attr_block_diff_summary(
        map_sources,
        sample_root=tmp_path / "samples",
        mapping_profile="exe_compat_v2",
        block_limit=2,
    )

    assert summary["map_count"] == 2
    assert summary["fully_matching_map_count"] == 2
    assert summary["total_compared_blocks"] == 4
    assert summary["total_mismatch_count"] == 0
    assert all(item["all_blocks_match"] for item in summary["maps"])
