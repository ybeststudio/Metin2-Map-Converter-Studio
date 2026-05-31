from __future__ import annotations

from app.core.map_reader import discover_map_sources, resolve_map_source_by_name
from app.core.stone_generator import build_stone_text


VALID_SETTING = """ScriptType\tMapSetting

CellScale\t200
HeightScale\t0.500000

ViewRadius\t128

MapSize\t1\t1
BasePosition\t0\t0
TextureSet\ttextureset\\test.txt
Environment\ttest.msenv
"""


def test_build_stone_text_prefers_matching_sample(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")

    sample_dir = tmp_path / "samples" / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "stone.txt").write_text(
        "m 100 200 150 200 0 0 2000s 100 1 8005\nr 110 210 100 100 0 0 3555s 100 1 2001\n",
        encoding="utf-8",
    )

    map_source = discover_map_sources(source_root)[0]
    text, source = build_stone_text(map_source, sample_root=tmp_path / "samples")

    assert text == (
        "m\t100\t200\t150\t200\t0\t0\t2000s\t100\t1\t8005\n"
        "r\t110\t210\t100\t100\t0\t0\t3555s\t100\t1\t2001\n"
    )
    assert source == "sample:metin2_map_test"


def test_build_stone_text_uses_parent_map_sample(tmp_path) -> None:
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
    (sample_dir / "stone.txt").write_text(
        "m 150 250 150 200 0 0 2000s 100 1 8005\n",
        encoding="utf-8",
    )

    map_source = resolve_map_source_by_name(source_root, "metin2_map_parent_pass")
    assert map_source is not None

    text, source = build_stone_text(map_source, sample_root=tmp_path / "samples")

    assert text == "m\t150\t250\t150\t200\t0\t0\t2000s\t100\t1\t8005\n"
    assert source == "sample:metin2_map_parent"


def test_build_stone_text_returns_empty_fallback_when_missing(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")

    map_source = discover_map_sources(source_root)[0]
    text, source = build_stone_text(map_source, sample_root=tmp_path / "samples")

    assert text == ""
    assert source == "empty_fallback"
