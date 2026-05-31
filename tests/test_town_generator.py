from __future__ import annotations

from app.core.map_reader import discover_map_sources, resolve_map_source_by_name
from app.core.town_generator import build_town_text


VALID_SETTING = """ScriptType\tMapSetting

CellScale\t200
HeightScale\t0.500000

ViewRadius\t128

MapSize\t1\t1
BasePosition\t0\t0
TextureSet\ttextureset\\test.txt
Environment\ttest.msenv
"""


def test_build_town_text_prefers_matching_sample(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")

    sample_dir = tmp_path / "samples" / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "Town.txt").write_text("100 200\n300 400\n", encoding="utf-8")

    map_source = discover_map_sources(source_root)[0]
    text, source = build_town_text(map_source, sample_root=tmp_path / "samples")

    assert text == "100\t200\n300\t400\n"
    assert source == "sample:metin2_map_test"


def test_build_town_text_uses_parent_map_sample_for_pass_maps(tmp_path) -> None:
    source_root = tmp_path / "client"

    parent_dir = source_root / "metin2_map_parent"
    parent_dir.mkdir(parents=True)
    (parent_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    parent_area = parent_dir / "000000"
    parent_area.mkdir()
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (parent_area / "attr.atr").write_bytes(attr_data)

    child_dir = source_root / "metin2_map_parent_pass"
    child_dir.mkdir(parents=True)
    (child_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    (child_dir / "mapproperty.txt").write_text(
        'ScriptType MapProperty\n\nParentMapName "metin2_map_parent"\n',
        encoding="utf-8",
    )

    sample_dir = tmp_path / "samples" / "metin2_map_parent"
    sample_dir.mkdir(parents=True)
    (sample_dir / "Town.txt").write_text("150 250\n", encoding="utf-8")

    map_source = resolve_map_source_by_name(source_root, "metin2_map_parent_pass")
    assert map_source is not None

    text, source = build_town_text(map_source, sample_root=tmp_path / "samples")

    assert text == "150\t250\n"
    assert source == "sample:metin2_map_parent"


def test_build_town_text_falls_back_to_setting_center(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(
        VALID_SETTING.replace("MapSize\t1\t1", "MapSize\t4\t5"),
        encoding="utf-8",
    )

    map_source = discover_map_sources(source_root)[0]
    text, source = build_town_text(map_source, sample_root=tmp_path / "samples")

    assert text == "512\t640\n"
    assert source == "setting_center_fallback"
