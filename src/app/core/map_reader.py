from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, List, Optional

from app.core.setting_parser import MapSetting, parse_setting_file


@dataclass(slots=True)
class MapSource:
    name: str
    path: Path
    setting_path: Path
    setting: MapSetting
    mapproperty_path: Path | None = None
    parent_map_name: str | None = None
    attr_source_map_name: str | None = None
    attr_source_path: Path | None = None
    area_directories: List[Path] = field(default_factory=list)
    attr_files: List[Path] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def area_grid_width(self) -> int:
        if not self.area_directories:
            return 0
        return max(_parse_area_coordinates(path)[0] for path in self.area_directories) + 1

    @property
    def area_grid_height(self) -> int:
        if not self.area_directories:
            return 0
        return max(_parse_area_coordinates(path)[1] for path in self.area_directories) + 1


def discover_map_sources(root_path: str | Path) -> List[MapSource]:
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Kaynak dizin bulunamadi: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Kaynak yol bir klasor olmali: {root}")

    sources: List[MapSource] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if not _looks_like_map_directory(child):
            continue

        map_source = _build_map_source(child)
        if map_source is not None:
            sources.append(map_source)

    return sources


def resolve_map_source_by_name(
    root_path: str | Path,
    map_name: str,
) -> MapSource | None:
    map_sources = discover_map_sources(root_path)
    source_index = {map_source.name: map_source for map_source in map_sources}
    return resolve_map_source_for_generation(
        source_index.get(map_name),
        source_index,
        requested_name=map_name,
    )


def resolve_map_source_for_generation(
    map_source: MapSource | None,
    source_index: dict[str, MapSource],
    requested_name: str | None = None,
    _seen: set[str] | None = None,
) -> MapSource | None:
    if _seen is None:
        _seen = set()

    if map_source is None:
        if requested_name and requested_name.endswith("_pass"):
            base_name = requested_name[:-5]
            if base_name and base_name not in _seen and base_name in source_index:
                _seen.add(base_name)
                base_source = resolve_map_source_for_generation(
                    source_index[base_name],
                    source_index,
                    requested_name=base_name,
                    _seen=_seen,
                )
                if base_source is None:
                    return None
                warnings = list(base_source.warnings)
                warnings.append(
                    f"Kaynak map bulunamadi; `{base_name}` uzerinden alias uretiliyor"
                )
                return replace(
                    base_source,
                    name=requested_name,
                    attr_source_map_name=base_source.attr_source_map_name or base_source.name,
                    attr_source_path=base_source.attr_source_path or base_source.path,
                    warnings=warnings,
                )
        return None

    if map_source.name in _seen:
        return map_source
    _seen.add(map_source.name)

    if map_source.attr_files:
        return map_source

    fallback_name = _resolve_fallback_map_name(map_source)
    if fallback_name and fallback_name in source_index and fallback_name not in _seen:
        fallback = resolve_map_source_for_generation(
            source_index[fallback_name],
            source_index,
            requested_name=fallback_name,
            _seen=_seen,
        )
        if fallback is not None:
            warnings = list(map_source.warnings) + list(fallback.warnings)
            warnings.append(
                f"Kaynak attr verisi `{fallback_name}` mapinden miras aliniyor"
            )
            return replace(
                map_source,
                attr_source_map_name=fallback.attr_source_map_name or fallback.name,
                attr_source_path=fallback.attr_source_path or fallback.path,
                area_directories=list(fallback.area_directories),
                attr_files=list(fallback.attr_files),
                warnings=warnings,
            )

    return map_source


def _build_map_source(map_dir: Path) -> Optional[MapSource]:
    setting_path = _find_setting_path(map_dir)
    if setting_path is None:
        return None

    setting = parse_setting_file(setting_path)
    mapproperty_path = _find_mapproperty_path(map_dir)
    parent_map_name = _parse_parent_map_name(mapproperty_path)
    area_directories = list(_iter_area_directories(map_dir))
    attr_files = [area_dir / "attr.atr" for area_dir in area_directories if (area_dir / "attr.atr").exists()]
    warnings: List[str] = []

    if not area_directories:
        warnings.append("Sayisal area klasoru bulunamadi")

    if area_directories and not attr_files:
        warnings.append("Area klasorleri bulundu ancak attr.atr dosyasi bulunamadi")

    return MapSource(
        name=map_dir.name,
        path=map_dir,
        setting_path=setting_path,
        setting=setting,
        mapproperty_path=mapproperty_path,
        parent_map_name=parent_map_name,
        attr_source_map_name=map_dir.name,
        attr_source_path=map_dir,
        area_directories=area_directories,
        attr_files=attr_files,
        warnings=warnings + list(setting.warnings),
    )


def _find_setting_path(map_dir: Path) -> Optional[Path]:
    for candidate_name in ("Setting.txt", "setting.txt"):
        candidate = map_dir / candidate_name
        if candidate.exists():
            return candidate
    return None


def _looks_like_map_directory(map_dir: Path) -> bool:
    if map_dir.name.startswith(("metin2_map_", "metin2_guild_", "map_", "gm_guild_")):
        return True
    return _find_setting_path(map_dir) is not None and any(_iter_area_directories(map_dir))


def _find_mapproperty_path(map_dir: Path) -> Optional[Path]:
    candidate = map_dir / "mapproperty.txt"
    if candidate.exists():
        return candidate
    return None


def _iter_area_directories(map_dir: Path) -> Iterable[Path]:
    for child in sorted(map_dir.iterdir()):
        if child.is_dir() and child.name.isdigit() and len(child.name) == 6:
            yield child


def _parse_area_coordinates(area_dir: Path) -> tuple[int, int]:
    name = area_dir.name
    return int(name[:3]), int(name[3:])


def _parse_parent_map_name(mapproperty_path: Path | None) -> str | None:
    if mapproperty_path is None:
        return None
    for raw_line in mapproperty_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if not parts or parts[0] != "ParentMapName":
            continue
        value = parts[1].strip().strip('"') if len(parts) == 2 else ""
        return value or None
    return None


def _resolve_fallback_map_name(map_source: MapSource) -> str | None:
    if map_source.parent_map_name:
        return map_source.parent_map_name
    if map_source.name.endswith("_pass"):
        base_name = map_source.name[:-5]
        if base_name:
            return base_name
    return None
