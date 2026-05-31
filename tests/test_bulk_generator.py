from __future__ import annotations

from app.core.bulk_generator import build_generation_summary, generate_bulk_outputs
from app.core.map_reader import discover_map_sources
from app.core.server_attr_exporter import is_lzo_backend_available


VALID_SETTING = """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

ViewRadius 128

MapSize 4 5
BasePosition 409600 896000
TextureSet textureset\\metin2_A1.txt
Environment A1.msenv
"""


def test_discover_map_sources_finds_valid_maps(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    (area_dir / "attr.atr").write_text("fake", encoding="utf-8")

    sources = discover_map_sources(source_root)

    assert len(sources) == 1
    assert sources[0].name == "metin2_map_test"
    assert len(sources[0].area_directories) == 1
    assert len(sources[0].attr_files) == 1


def test_generate_bulk_outputs_creates_expected_structure(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    output_root = tmp_path / "output"
    sample_root = tmp_path / "samples"
    exportable_setting = VALID_SETTING.replace("MapSize 4 5", "MapSize 1 1")

    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(exportable_setting, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)
    sample_dir = sample_root / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "boss.txt").write_text(
        "g 100 200 100 100 0 0 1000s 100 1 317\n",
        encoding="utf-8",
    )
    (sample_dir / "Town.txt").write_text("100 200\n", encoding="utf-8")
    (sample_dir / "regen.txt").write_text(
        "r 100 200 10 10 0 0 5s 100 1 101\n",
        encoding="utf-8",
    )
    (sample_dir / "npc.txt").write_text(
        "// NPC\nm 100 200 0 0 0 1 1m 100 1 20300\n",
        encoding="utf-8",
    )
    (sample_dir / "stone.txt").write_text(
        "m 100 200 150 200 0 0 2000s 100 1 8005\n",
        encoding="utf-8",
    )

    sources = discover_map_sources(source_root)
    results = generate_bulk_outputs(sources, output_root, sample_root=sample_root)

    generated_map_dir = output_root / "metin2_map_test"
    assert len(results) == 1
    assert (generated_map_dir / "Setting.txt").exists()
    assert (generated_map_dir / "boss.txt").exists()
    assert (generated_map_dir / "npc.txt").exists()
    assert (generated_map_dir / "regen.txt").exists()
    assert (generated_map_dir / "stone.txt").exists()
    assert (generated_map_dir / "Town.txt").exists()
    assert (generated_map_dir / "server_attr").exists()
    assert not (generated_map_dir / "generation_report.json").exists()
    assert (
        (generated_map_dir / "Setting.txt").read_text(encoding="utf-8").splitlines()[0]
        == "ScriptType\tMapSetting"
    )
    assert (generated_map_dir / "Town.txt").read_text(encoding="utf-8") == "100\t200\n"
    assert (
        (generated_map_dir / "regen.txt").read_text(encoding="utf-8")
        == "r\t100\t200\t10\t10\t0\t0\t5s\t100\t1\t101\n"
    )
    assert (
        (generated_map_dir / "boss.txt").read_text(encoding="utf-8")
        == "g\t100\t200\t100\t100\t0\t0\t1000s\t100\t1\t317\n"
    )
    assert (
        (generated_map_dir / "npc.txt").read_text(encoding="utf-8")
        == "// NPC\nm\t100\t200\t0\t0\t0\t1\t1m\t100\t1\t20300\n"
    )
    assert (
        (generated_map_dir / "stone.txt").read_text(encoding="utf-8")
        == "m\t100\t200\t150\t200\t0\t0\t2000s\t100\t1\t8005\n"
    )

    report = results[0].report
    assert report["boss_source"] == "sample:metin2_map_test"
    assert report["npc_source"] == "sample:metin2_map_test"
    assert report["regen_source"] == "sample:metin2_map_test"
    assert report["stone_source"] == "sample:metin2_map_test"
    assert report["town_source"] == "sample:metin2_map_test"
    assert report["server_attr_status"] == "EXPORTED"
    assert report["server_attr_error"] is None

    summary = build_generation_summary(results)
    assert summary["map_count"] == 1


def test_build_generation_summary_includes_status_and_missing_maps(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    output_root = tmp_path / "output"
    sample_root = tmp_path / "samples"
    exportable_setting = VALID_SETTING.replace("MapSize 4 5", "MapSize 1 1")

    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(exportable_setting, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_dir = sample_root / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "boss.txt").write_text("g 100 200 100 100 0 0 1000s 100 1 317\n", encoding="utf-8")
    (sample_dir / "Town.txt").write_text("100 200\n", encoding="utf-8")
    (sample_dir / "regen.txt").write_text("r 100 200 10 10 0 0 5s 100 1 101\n", encoding="utf-8")
    (sample_dir / "npc.txt").write_text("// NPC\nm 100 200 0 0 0 1 1m 100 1 20300\n", encoding="utf-8")
    (sample_dir / "stone.txt").write_text("m 100 200 150 200 0 0 2000s 100 1 8005\n", encoding="utf-8")

    sources = discover_map_sources(source_root)
    results = generate_bulk_outputs(sources, output_root, sample_root=sample_root)
    summary = build_generation_summary(
        results,
        requested_map_names=["metin2_map_test", "metin2_map_missing"],
        missing_requested_maps=["metin2_map_missing"],
    )

    assert summary["requested_map_count"] == 2
    assert summary["generated_map_count"] == 1
    assert summary["missing_requested_map_count"] == 1
    assert summary["missing_requested_maps"] == ["metin2_map_missing"]
    assert summary["server_attr_status_counts"]["EXPORTED"] == 1
    assert summary["boss_source_counts"]["sample:metin2_map_test"] == 1
