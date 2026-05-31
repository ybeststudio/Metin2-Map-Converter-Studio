from __future__ import annotations

import textwrap

import pytest

from app.core.setting_parser import (
    SettingParseError,
    parse_setting_text,
)


def test_parse_valid_setting() -> None:
    content = textwrap.dedent(
        """
        ScriptType MapSetting

        CellScale 200
        HeightScale 0.500000

        ViewRadius 128

        MapSize 4 4
        BasePosition 921600 204800
        TextureSet textureset\\metin2_a1.txt
        Environment a1.msenv
        """
    ).strip()

    setting = parse_setting_text(content)

    assert setting.script_type == "MapSetting"
    assert setting.cell_scale == 200
    assert setting.height_scale == 0.5
    assert setting.view_radius == 128
    assert setting.map_size == (4, 4)
    assert setting.base_position == (921600, 204800)
    assert setting.texture_set == r"textureset\metin2_a1.txt"
    assert setting.environment == "a1.msenv"
    assert setting.warnings == []


def test_missing_optional_values_create_warnings() -> None:
    content = textwrap.dedent(
        """
        ScriptType MapSetting
        CellScale 200
        HeightScale 0.5
        MapSize 8 8
        BasePosition 0 0
        """
    ).strip()

    setting = parse_setting_text(content)

    assert "TextureSet alani bulunamadi" in setting.warnings
    assert "Environment alani bulunamadi" in setting.warnings


def test_duplicate_keys_raise_error() -> None:
    content = textwrap.dedent(
        """
        ScriptType MapSetting
        CellScale 200
        HeightScale 0.5
        MapSize 4 4
        BasePosition 0 0
        CellScale 300
        """
    ).strip()

    with pytest.raises(SettingParseError, match="Tekrarlanan anahtar"):
        parse_setting_text(content)


def test_invalid_map_size_raises_error() -> None:
    content = textwrap.dedent(
        """
        ScriptType MapSetting
        CellScale 200
        HeightScale 0.5
        MapSize 4
        BasePosition 0 0
        """
    ).strip()

    with pytest.raises(SettingParseError, match="MapSize iki sayisal deger"):
        parse_setting_text(content)


def test_to_server_format_preserves_expected_fields() -> None:
    content = textwrap.dedent(
        """
        ScriptType MapSetting
        CellScale 200
        HeightScale 0.5
        MapSize 4 4
        BasePosition 100 200
        TextureSet textureset\\metin2_a1.txt
        Environment a1.msenv
        """
    ).strip()

    setting = parse_setting_text(content)

    assert setting.to_server_format() == textwrap.dedent(
        """
        ScriptType\tMapSetting

        CellScale\t200
        HeightScale\t0.500000

        MapSize\t4\t4
        BasePosition\t100\t200
        TextureSet\ttextureset\\metin2_a1.txt
        Environment\ta1.msenv
        """
    ).lstrip()
