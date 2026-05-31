from __future__ import annotations

from app.core.generation_workflow import run_selected_generation
from app.core.server_attr_exporter import is_lzo_backend_available


VALID_SETTING = """ScriptType\tMapSetting

CellScale\t200
HeightScale\t0.500000

ViewRadius\t128

MapSize\t1\t1
BasePosition\t0\t0
TextureSet\ttextureset\\test.txt
Environment\ttest.msenv
"""


def test_run_selected_generation_reports_generated_and_missing_maps(tmp_path) -> None:
    assert is_lzo_backend_available() is True

    source_root = tmp_path / "client"
    output_root = tmp_path / "output"
    sample_root = tmp_path / "samples"
    report_file = tmp_path / "analysis" / "summary.json"

    map_dir = source_root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (area_dir / "attr.atr").write_bytes(attr_data)

    sample_dir = sample_root / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "boss.txt").write_text("g 100 200 100 100 0 0 1000s 100 1 317\n", encoding="utf-8")
    (sample_dir / "Town.txt").write_text("100 200\n", encoding="utf-8")
    (sample_dir / "regen.txt").write_text("r 100 200 10 10 0 0 5s 100 1 101\n", encoding="utf-8")
    (sample_dir / "npc.txt").write_text("// NPC\nm 100 200 0 0 0 1 1m 100 1 20300\n", encoding="utf-8")
    (sample_dir / "stone.txt").write_text("m 100 200 150 200 0 0 2000s 100 1 8005\n", encoding="utf-8")

    result = run_selected_generation(
        source_root=source_root,
        output_root=output_root,
        requested_map_names=["metin2_map_test", "metin2_map_missing"],
        sample_root=sample_root,
        report_file=report_file,
    )

    assert result.generated_map_count == 1
    assert result.missing_requested_maps == ["metin2_map_missing"]
    assert result.summary["server_attr_status_counts"]["EXPORTED"] == 1
    assert result.report_path.exists()
