from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class SettingParseError(ValueError):
    """Raised when a Metin2 map Setting.txt file cannot be parsed."""


@dataclass(slots=True)
class MapSetting:
    script_type: str = "MapSetting"
    cell_scale: int = 200
    height_scale: float = 0.5
    view_radius: Optional[int] = None
    map_size: tuple[int, int] = (0, 0)
    base_position: tuple[int, int] = (0, 0)
    texture_set: Optional[str] = None
    environment: Optional[str] = None
    extras: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.map_size[0]

    @property
    def height(self) -> int:
        return self.map_size[1]

    @property
    def base_x(self) -> int:
        return self.base_position[0]

    @property
    def base_y(self) -> int:
        return self.base_position[1]

    def to_server_format(self) -> str:
        separator = "\t"
        lines = [
            f"ScriptType{separator}{self.script_type}",
            "",
            f"CellScale{separator}{self.cell_scale}",
            f"HeightScale{separator}{self.height_scale:.6f}",
            "",
        ]

        if self.view_radius is not None:
            lines.append(f"ViewRadius{separator}{self.view_radius}")
            lines.append("")

        lines.extend(
            [
                f"MapSize{separator}{self.width}{separator}{self.height}",
                f"BasePosition{separator}{self.base_x}{separator}{self.base_y}",
            ]
        )

        if self.texture_set:
            lines.append(f"TextureSet{separator}{self.texture_set}")

        if self.environment:
            lines.append(f"Environment{separator}{self.environment}")

        for key, value in self.extras.items():
            if value:
                lines.append(f"{key}{separator}{value}".rstrip())
            else:
                lines.append(key)

        return "\n".join(lines).strip() + "\n"


REQUIRED_KEYS = {
    "ScriptType",
    "CellScale",
    "HeightScale",
    "MapSize",
    "BasePosition",
}


def parse_setting_text(text: str) -> MapSetting:
    tokens = list(_iter_setting_lines(text.splitlines()))
    data: Dict[str, str] = {}

    for key, value in tokens:
        if key in data:
            raise SettingParseError(f"Tekrarlanan anahtar bulundu: {key}")
        data[key] = value

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise SettingParseError(
            "Zorunlu alanlar eksik: " + ", ".join(sorted(missing))
        )

    setting = MapSetting(
        script_type=_parse_single_value(data, "ScriptType"),
        cell_scale=_parse_int(data, "CellScale"),
        height_scale=_parse_float(data, "HeightScale"),
        view_radius=_parse_optional_int(data, "ViewRadius"),
        map_size=_parse_int_pair(data, "MapSize"),
        base_position=_parse_int_pair(data, "BasePosition"),
        texture_set=data.get("TextureSet"),
        environment=data.get("Environment"),
        extras={
            key: value
            for key, value in data.items()
            if key
            not in {
                "ScriptType",
                "CellScale",
                "HeightScale",
                "ViewRadius",
                "MapSize",
                "BasePosition",
                "TextureSet",
                "Environment",
            }
        },
    )

    if setting.script_type != "MapSetting":
        setting.warnings.append(
            f"Beklenmeyen ScriptType bulundu: {setting.script_type}"
        )

    if setting.width <= 0 or setting.height <= 0:
        raise SettingParseError("MapSize degerleri sifirdan buyuk olmalidir")

    if setting.cell_scale <= 0:
        raise SettingParseError("CellScale sifirdan buyuk olmalidir")

    if setting.texture_set is None:
        setting.warnings.append("TextureSet alani bulunamadi")

    if setting.environment is None:
        setting.warnings.append("Environment alani bulunamadi")

    return setting


def parse_setting_file(file_path: str | Path) -> MapSetting:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Setting dosyasi bulunamadi: {path}")
    return parse_setting_text(path.read_text(encoding="utf-8"))


def _iter_setting_lines(lines: Iterable[str]) -> Iterable[tuple[str, str]]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("//") or line.startswith("#"):
            continue

        parts = line.split(maxsplit=1)
        key = parts[0]
        value = parts[1].strip() if len(parts) == 2 else ""
        yield key, value


def _parse_single_value(data: Dict[str, str], key: str) -> str:
    value = data[key].strip()
    if not value:
        raise SettingParseError(f"{key} alani bos olamaz")
    return value


def _parse_int(data: Dict[str, str], key: str) -> int:
    try:
        return int(_parse_single_value(data, key))
    except ValueError as exc:
        raise SettingParseError(f"{key} sayisal bir deger olmali") from exc


def _parse_optional_int(data: Dict[str, str], key: str) -> Optional[int]:
    if key not in data:
        return None
    return _parse_int(data, key)


def _parse_float(data: Dict[str, str], key: str) -> float:
    try:
        return float(_parse_single_value(data, key))
    except ValueError as exc:
        raise SettingParseError(f"{key} ondalikli bir deger olmali") from exc


def _parse_int_pair(data: Dict[str, str], key: str) -> tuple[int, int]:
    parts = _parse_single_value(data, key).split()
    if len(parts) != 2:
        raise SettingParseError(f"{key} iki sayisal deger icermeli")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise SettingParseError(f"{key} iki sayisal deger icermeli") from exc
