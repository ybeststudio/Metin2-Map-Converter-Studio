from __future__ import annotations

from dataclasses import dataclass

from app.core.setting_parser import MapSetting


MAP_TILE_CELLS = 128
SECTREE_SIZE = 6400
CELL_SIZE = 50


@dataclass(slots=True)
class MapGeometry:
    map_width_tiles: int
    map_height_tiles: int
    cell_scale: int
    base_x: int
    base_y: int

    @property
    def pixel_width(self) -> int:
        return self.cell_scale * MAP_TILE_CELLS * self.map_width_tiles

    @property
    def pixel_height(self) -> int:
        return self.cell_scale * MAP_TILE_CELLS * self.map_height_tiles

    @property
    def sectree_width(self) -> int:
        return _ceil_div(self.pixel_width, SECTREE_SIZE)

    @property
    def sectree_height(self) -> int:
        return _ceil_div(self.pixel_height, SECTREE_SIZE)

    @property
    def cells_per_sectree_axis(self) -> int:
        return SECTREE_SIZE // CELL_SIZE

    @property
    def dword_count_per_sectree(self) -> int:
        axis = self.cells_per_sectree_axis
        return axis * axis


def geometry_from_setting(setting: MapSetting) -> MapGeometry:
    return MapGeometry(
        map_width_tiles=setting.width,
        map_height_tiles=setting.height,
        cell_scale=setting.cell_scale,
        base_x=setting.base_x,
        base_y=setting.base_y,
    )


def local_to_global(local_x: int, local_y: int, setting: MapSetting) -> tuple[int, int]:
    return (
        setting.base_x + local_x * setting.cell_scale,
        setting.base_y + local_y * setting.cell_scale,
    )


def global_to_local(global_x: int, global_y: int, setting: MapSetting) -> tuple[int, int]:
    return (
        (global_x - setting.base_x) // setting.cell_scale,
        (global_y - setting.base_y) // setting.cell_scale,
    )


def _ceil_div(left: int, right: int) -> int:
    return (left + right - 1) // right
