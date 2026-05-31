from __future__ import annotations

from app.core.coordinate import geometry_from_setting, global_to_local, local_to_global
from app.core.setting_parser import parse_setting_text


def test_geometry_from_setting_calculates_server_attr_sectree_grid() -> None:
    setting = parse_setting_text(
        """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

MapSize 4 5
BasePosition 409600 896000
TextureSet textureset\\metin2_A1.txt
Environment A1.msenv
"""
    )

    geometry = geometry_from_setting(setting)

    assert geometry.pixel_width == 102400
    assert geometry.pixel_height == 128000
    assert geometry.sectree_width == 16
    assert geometry.sectree_height == 20
    assert geometry.dword_count_per_sectree == 16384


def test_coordinate_conversion_round_trip() -> None:
    setting = parse_setting_text(
        """ScriptType MapSetting

CellScale 200
HeightScale 0.500000

MapSize 4 5
BasePosition 409600 896000
TextureSet textureset\\metin2_A1.txt
Environment A1.msenv
"""
    )

    global_x, global_y = local_to_global(597, 682, setting)
    assert (global_x, global_y) == (529000, 1032400)
    assert global_to_local(global_x, global_y, setting) == (597, 682)
