from __future__ import annotations

from app.core.map_reader import discover_map_sources
from app.core.server_attr_analyzer import (
    build_attr_analysis_report,
    find_matching_server_attr_sample,
    is_lzo_backend_available,
    validate_server_attr_lzo_blocks,
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


def test_build_attr_analysis_report_includes_attr_summary(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    report = build_attr_analysis_report(map_source)

    assert report["map_name"] == "metin2_map_test"
    assert report["attr_file_count"] == 1
    assert report["attr_layout_consistent"] is True
    assert report["attr_unique_values"] == [1]
    assert report["attr_tiles"][0]["header_hex"] == "4a0a00010001"
    assert report["geometry"]["sectree_width"] == 4
    assert report["geometry"]["sectree_height"] == 4


def test_build_attr_analysis_report_compares_server_attr_sample(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x00" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_root = tmp_path / "samples" / "metin2_map_test"
    sample_root.mkdir(parents=True)
    map_source = discover_map_sources(source_root)[0]
    export_server_attr(map_source, sample_root / "server_attr")
    report = build_attr_analysis_report(
        map_source,
        sample_root / "server_attr",
    )

    assert report["server_attr_sample"]["sectree_width"] == 4
    assert report["server_attr_sample"]["sectree_height"] == 4
    assert report["server_attr_sample"]["block_count"] == 16
    assert report["comparison"]["server_attr_sample_header_match"] is True
    assert report["comparison"]["lzo_backend_available"] is True
    assert report["comparison"]["block_decompression_ready"] is True


def test_validate_server_attr_lzo_blocks_decompresses_exported_blocks(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    output_file = tmp_path / "server_attr"
    export_server_attr(map_source, output_file)

    validation = validate_server_attr_lzo_blocks(output_file, block_limit=2)

    assert validation["lzo_backend_available"] is True
    assert validation["validated_block_count"] == 2
    assert all(block["decompressed_size_matches"] for block in validation["blocks"])


def test_find_matching_server_attr_sample_falls_back_from_pass_to_base(tmp_path) -> None:
    sample_dir = tmp_path / "samples" / "metin2_map_demo"
    sample_dir.mkdir(parents=True)
    sample_file = sample_dir / "server_attr"
    sample_file.write_bytes(b"12345678")

    assert (
        find_matching_server_attr_sample("metin2_map_demo_pass", tmp_path / "samples")
        == sample_file
    )
