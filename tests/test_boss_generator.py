from __future__ import annotations

from app.core.boss_generator import build_boss_text
from app.core.map_reader import discover_map_sources, resolve_map_source_by_name


VALID_SETTING = """ScriptType\tMapSetting

CellScale\t200
HeightScale\t0.500000

ViewRadius\t128

MapSize\t1\t1
BasePosition\t0\t0
TextureSet\ttextureset\\test.txt
Environment\ttest.msenv
"""


def test_build_boss_text_prefers_matching_sample(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")

    sample_dir = tmp_path / "samples" / "metin2_map_test"
    sample_dir.mkdir(parents=True)
    (sample_dir / "boss.txt").write_text(
        "g 100 200 100 100 0 0 1000s 100 1 317\nm 110 210 100 100 0 0 600s 100 1 151\n",
        encoding="utf-8",
    )

    map_source = discover_map_sources(source_root)[0]
    text, source = build_boss_text(map_source, sample_root=tmp_path / "samples")

    assert text == (
        "g\t100\t200\t100\t100\t0\t0\t1000s\t100\t1\t317\n"
        "m\t110\t210\t100\t100\t0\t0\t600s\t100\t1\t151\n"
    )
    assert source == "sample:metin2_map_test"


def test_build_boss_text_uses_parent_map_sample(tmp_path) -> None:
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
    (sample_dir / "boss.txt").write_text(
        "g 150 250 100 100 0 0 1000s 100 1 317\n",
        encoding="utf-8",
    )

    map_source = resolve_map_source_by_name(source_root, "metin2_map_parent_pass")
    assert map_source is not None

    text, source = build_boss_text(map_source, sample_root=tmp_path / "samples")

    assert text == "g\t150\t250\t100\t100\t0\t0\t1000s\t100\t1\t317\n"
    assert source == "sample:metin2_map_parent"


def test_build_boss_text_returns_empty_fallback_when_missing(tmp_path) -> None:
    source_root = tmp_path / "client"
    map_dir = source_root / "metin2_map_test"
    map_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")

    map_source = discover_map_sources(source_root)[0]
    text, source = build_boss_text(map_source, sample_root=tmp_path / "samples")

    assert text == ""
    assert source == "empty_fallback"
