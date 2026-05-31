from __future__ import annotations
from pathlib import Path

from app.gui import (
    build_map_records,
    build_selection_summary_text,
    filter_map_records,
    format_map_record_detail,
    discover_available_map_names,
    merge_map_names,
    parse_map_names,
)


def test_parse_map_names_ignores_empty_comment_and_duplicate_lines() -> None:
    raw_text = """
    # yorum
    metin2_map_a1

    metin2_map_a1
    metin2_map_b1
    """

    assert parse_map_names(raw_text) == ["metin2_map_a1", "metin2_map_b1"]


def test_merge_map_names_preserves_order_and_uniqueness() -> None:
    assert merge_map_names(
        ["metin2_map_a1"],
        ["metin2_map_a1", "metin2_map_b1", " metin2_map_c1 "],
    ) == ["metin2_map_a1", "metin2_map_b1", "metin2_map_c1"]


def test_discover_available_map_names_returns_sorted_map_names(tmp_path) -> None:
    root = tmp_path / "client"
    for name in ("metin2_map_b1", "metin2_map_a1"):
        map_dir = root / name
        map_dir.mkdir(parents=True)
        (map_dir / "setting.txt").write_text(
            "ScriptType\tMapSetting\n\nCellScale\t200\nHeightScale\t0.500000\n\nViewRadius\t128\n\nMapSize\t1\t1\nBasePosition\t0\t0\nTextureSet\ttextureset\\test.txt\nEnvironment\ttest.msenv\n",
            encoding="utf-8",
        )

    assert discover_available_map_names(root) == ["metin2_map_a1", "metin2_map_b1"]


def test_build_map_records_collects_area_attr_and_warning_metadata(tmp_path) -> None:
    root = tmp_path / "client"
    map_dir = root / "metin2_map_test"
    area_dir = map_dir / "000000"
    area_dir.mkdir(parents=True)
    (map_dir / "setting.txt").write_text(
        "ScriptType\tMapSetting\n\nCellScale\t200\nHeightScale\t0.500000\n\nViewRadius\t128\n\nMapSize\t2\t3\nBasePosition\t100\t200\nTextureSet\ttextureset\\test.txt\nEnvironment\ttest.msenv\n",
        encoding="utf-8",
    )
    (map_dir / "mapproperty.txt").write_text('ParentMapName "metin2_map_base"\n', encoding="utf-8")
    (area_dir / "attr.atr").write_bytes(b"dummy")

    records = build_map_records(root)

    assert len(records) == 1
    record = records[0]
    assert record.name == "metin2_map_test"
    assert record.parent_map_name == "metin2_map_base"
    assert record.map_size == (2, 3)
    assert record.base_position == (100, 200)
    assert record.area_count == 1
    assert record.attr_count == 1
    assert record.area_grid_size == (1, 1)
    assert record.path == Path(map_dir)


def test_filter_map_records_supports_query_attr_and_warning_filters(tmp_path) -> None:
    root = tmp_path / "client"

    map_ok = root / "metin2_map_alpha"
    map_ok_area = map_ok / "000000"
    map_ok_area.mkdir(parents=True)
    (map_ok / "setting.txt").write_text(
        "ScriptType\tMapSetting\n\nCellScale\t200\nHeightScale\t0.500000\n\nViewRadius\t128\n\nMapSize\t1\t1\nBasePosition\t0\t0\nTextureSet\ttextureset\\alpha.txt\nEnvironment\talpha.msenv\n",
        encoding="utf-8",
    )
    (map_ok_area / "attr.atr").write_bytes(b"dummy")

    map_warning = root / "metin2_map_beta"
    (map_warning / "000000").mkdir(parents=True)
    (map_warning / "setting.txt").write_text(
        "ScriptType\tMapSetting\n\nCellScale\t200\nHeightScale\t0.500000\n\nViewRadius\t128\n\nMapSize\t1\t1\nBasePosition\t0\t0\n",
        encoding="utf-8",
    )

    records = build_map_records(root)

    assert [record.name for record in filter_map_records(records, "alpha")] == ["metin2_map_alpha"]
    assert [record.name for record in filter_map_records(records, only_with_attr=True)] == ["metin2_map_alpha"]
    assert [record.name for record in filter_map_records(records, only_with_warnings=True)] == [
        "metin2_map_beta"
    ]


def test_format_map_record_detail_contains_selected_map_summary(tmp_path) -> None:
    root = tmp_path / "client"
    map_dir = root / "metin2_map_detail"
    (map_dir / "000000").mkdir(parents=True)
    (map_dir / "setting.txt").write_text(
        "ScriptType\tMapSetting\n\nCellScale\t200\nHeightScale\t0.500000\n\nViewRadius\t128\n\nMapSize\t4\t5\nBasePosition\t409600\t896000\nTextureSet\ttextureset\\metin2_A1.txt\nEnvironment\tA1.msenv\n",
        encoding="utf-8",
    )

    record = build_map_records(root)[0]
    detail = format_map_record_detail(record)

    assert "Map Adı: metin2_map_detail" in detail
    assert "MapSize: 4 x 5" in detail
    assert "BasePosition: 409600, 896000" in detail


def test_build_selection_summary_text_contains_selected_and_requested_counts() -> None:
    assert build_selection_summary_text(3, 7) == "Seçili map: 3 | Üretim kuyruğu: 7"
