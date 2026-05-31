from __future__ import annotations

from app.core.map_reader import resolve_map_source_by_name


VALID_SETTING = """ScriptType\tMapSetting

CellScale\t200
HeightScale\t0.500000

ViewRadius\t128

MapSize\t1\t1
BasePosition\t0\t0
TextureSet\ttextureset\\test.txt
Environment\ttest.msenv
"""


def test_resolve_map_source_by_name_inherits_parent_attr_files(tmp_path) -> None:
    source_root = tmp_path / "client"

    parent_dir = source_root / "metin2_map_parent"
    parent_area = parent_dir / "000000"
    parent_area.mkdir(parents=True)
    (parent_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (parent_area / "attr.atr").write_bytes(attr_data)

    child_dir = source_root / "metin2_map_child_pass"
    child_dir.mkdir(parents=True)
    (child_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    (child_dir / "mapproperty.txt").write_text(
        'ScriptType MapProperty\n\nParentMapName "metin2_map_parent"\n',
        encoding="utf-8",
    )

    resolved = resolve_map_source_by_name(source_root, "metin2_map_child_pass")

    assert resolved is not None
    assert resolved.name == "metin2_map_child_pass"
    assert len(resolved.attr_files) == 1
    assert resolved.attr_files[0].parent.name == "000000"
    assert resolved.attr_source_map_name == "metin2_map_parent"
    assert resolved.attr_source_path == parent_dir
    assert any("miras aliniyor" in warning for warning in resolved.warnings)


def test_resolve_map_source_by_name_aliases_missing_pass_suffix_to_base_map(tmp_path) -> None:
    source_root = tmp_path / "client"

    base_dir = source_root / "metin2_map_demo"
    base_area = base_dir / "000000"
    base_area.mkdir(parents=True)
    (base_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (base_area / "attr.atr").write_bytes(attr_data)

    resolved = resolve_map_source_by_name(source_root, "metin2_map_demo_pass")

    assert resolved is not None
    assert resolved.name == "metin2_map_demo_pass"
    assert len(resolved.attr_files) == 1
    assert resolved.attr_source_map_name == "metin2_map_demo"
    assert resolved.attr_source_path == base_dir
    assert any("alias uretiliyor" in warning for warning in resolved.warnings)


def test_resolve_map_source_by_name_supports_non_metin2_parent_map(tmp_path) -> None:
    source_root = tmp_path / "client"

    parent_dir = source_root / "map_n_threeway"
    parent_area = parent_dir / "000000"
    parent_area.mkdir(parents=True)
    (parent_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    attr_data = bytes.fromhex("4a0a00010001") + (b"\x01" * 65536)
    (parent_area / "attr.atr").write_bytes(attr_data)

    child_dir = source_root / "metin2_map_smhgate_threeway"
    child_dir.mkdir(parents=True)
    (child_dir / "setting.txt").write_text(VALID_SETTING, encoding="utf-8")
    (child_dir / "mapproperty.txt").write_text(
        'ScriptType MapProperty\n\nParentMapName "map_n_threeway"\n',
        encoding="utf-8",
    )

    resolved = resolve_map_source_by_name(source_root, "metin2_map_smhgate_threeway")

    assert resolved is not None
    assert resolved.name == "metin2_map_smhgate_threeway"
    assert len(resolved.attr_files) == 1
    assert resolved.attr_source_map_name == "map_n_threeway"
    assert resolved.attr_source_path == parent_dir
