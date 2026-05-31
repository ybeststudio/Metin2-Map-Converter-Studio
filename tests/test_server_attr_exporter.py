from __future__ import annotations

from app.core.map_reader import discover_map_sources
from app.core.server_attr_analyzer import analyze_server_attr_file
from app.core.server_attr_exporter import (
    export_server_attr_batch,
    is_lzo_backend_available,
    write_server_attr_export_report,
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


def test_write_server_attr_export_report_exports_valid_server_attr(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    payload = bytes([0, 1]) + (b"\x00" * (65536 - 2))
    attr_data = bytes.fromhex("4a0a00010001") + payload
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_root = tmp_path / "samples" / "metin2_map_test"
    sample_root.mkdir(parents=True)
    fake_sample = (4).to_bytes(4, "little") + (4).to_bytes(4, "little")
    for _ in range(16):
        fake_sample += (0).to_bytes(4, "little")
    (sample_root / "server_attr").write_bytes(fake_sample)

    map_source = discover_map_sources(source_root)[0]
    output_file = tmp_path / "output" / "server_attr"
    report_file = tmp_path / "output" / "server_attr_report.json"
    write_server_attr_export_report(
        map_source,
        output_file=output_file,
        report_file=report_file,
        sample_root=tmp_path / "samples",
    )

    exported = analyze_server_attr_file(output_file)
    assert exported.sectree_width == 4
    assert exported.sectree_height == 4
    assert exported.block_count == 16
    assert all(size > 0 for size in exported.first_block_sizes)


def test_export_server_attr_batch_exports_multiple_maps(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    for map_name, value in (("metin2_map_test_1", 0), ("metin2_map_test_2", 201)):
        map_dir = source_root / map_name
        area_dir = map_dir / "000000"
        area_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
        attr_data = bytes.fromhex("4a0a00010001") + (bytes([value]) * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_sources = discover_map_sources(source_root)
    summary = export_server_attr_batch(map_sources, output_root=tmp_path / "exports")

    assert summary["map_count"] == 2
    assert summary["maps"][0]["validation"]["block_count_matches"] is True


def test_export_server_attr_batch_accepts_sparse_setting_layouts(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"

    valid_map = source_root / "metin2_map_valid"
    valid_area = valid_map / "000000"
    valid_area.mkdir(parents=True)
    (valid_map / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    valid_attr = bytes.fromhex("4a0a00010001") + (b"\x00" * 65536)
    (valid_area / "attr.atr").write_bytes(valid_attr)

    sparse_map = source_root / "metin2_map_sparse"
    sparse_area = sparse_map / "000002"
    sparse_area.mkdir(parents=True)
    sparse_setting = VALID_SETTING.replace("MapSize 1 1", "MapSize 4 5")
    (sparse_map / "setting.txt").write_text(sparse_setting, encoding="utf-8")
    (sparse_area / "attr.atr").write_bytes(valid_attr)

    map_sources = discover_map_sources(source_root)
    summary = export_server_attr_batch(map_sources, output_root=tmp_path / "exports")

    assert summary["map_count"] == 2
    assert summary["skipped_map_count"] == 0


def test_export_server_attr_supports_sparse_area_coordinates(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_sparse"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(
        VALID_SETTING.replace("MapSize 1 1", "MapSize 4 5"),
        encoding="utf-8",
    )

    for area_name in ("000002", "001000", "002002"):
        area_dir = map_dir / area_name
        area_dir.mkdir(parents=True)
        attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
        (area_dir / "attr.atr").write_bytes(attr_data)

    map_source = discover_map_sources(source_root)[0]
    output_file = tmp_path / "output" / "server_attr"
    report_file = tmp_path / "output" / "server_attr_report.json"
    write_server_attr_export_report(
        map_source,
        output_file=output_file,
        report_file=report_file,
    )

    exported = analyze_server_attr_file(output_file)
    assert exported.sectree_width == 16
    assert exported.sectree_height == 20
    assert exported.block_count == 320
