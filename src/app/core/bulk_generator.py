from __future__ import annotations

import json
import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.core.boss_generator import build_boss_text
from app.core.map_reader import MapSource, resolve_map_source_for_generation
from app.core.npc_generator import build_npc_text
from app.core.regen_generator import build_regen_text
from app.core.server_attr_exporter import export_server_attr, is_lzo_backend_available
from app.core.server_attr_analyzer import analyze_server_attr_file
from app.core.stone_generator import build_stone_text
from app.core.town_generator import build_town_text


PLACEHOLDER_FILES = {}

try:
    import lzo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    lzo = None


@dataclass(slots=True)
class MapGenerationResult:
    map_name: str
    output_path: Path
    files_written: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


def generate_bulk_outputs(
    map_sources: List[MapSource],
    output_root: str | Path,
    sample_root: str | Path | None = None,
) -> List[MapGenerationResult]:
    output_root_path = Path(output_root)
    output_root_path.mkdir(parents=True, exist_ok=True)

    source_index = {map_source.name: map_source for map_source in map_sources}
    results: List[MapGenerationResult] = []
    for map_source in map_sources:
        resolved = resolve_map_source_for_generation(map_source, source_index)
        if resolved is None:
            continue
        results.append(
            generate_map_output(
                resolved,
                output_root_path,
                sample_root=sample_root,
            )
        )

    return results


def generate_map_output(
    map_source: MapSource,
    output_root: str | Path,
    sample_root: str | Path | None = None,
) -> MapGenerationResult:
    output_dir = Path(output_root) / map_source.name
    output_dir.mkdir(parents=True, exist_ok=True)

    result = MapGenerationResult(
        map_name=map_source.name,
        output_path=output_dir,
        warnings=list(map_source.warnings),
    )

    setting_target = output_dir / "Setting.txt"
    setting_target.write_text(
        map_source.setting.to_server_format(),
        encoding="utf-8",
    )
    result.files_written.append(setting_target.name)

    for file_name, content in PLACEHOLDER_FILES.items():
        target = output_dir / file_name
        target.write_text(content, encoding="utf-8")
        result.files_written.append(file_name)

    boss_text, boss_source = build_boss_text(map_source, sample_root=sample_root)
    boss_target = output_dir / "boss.txt"
    boss_target.write_text(boss_text, encoding="utf-8")
    result.files_written.append("boss.txt")

    npc_text, npc_source = build_npc_text(map_source, sample_root=sample_root)
    npc_target = output_dir / "npc.txt"
    npc_target.write_text(npc_text, encoding="utf-8")
    result.files_written.append("npc.txt")

    regen_text, regen_source = build_regen_text(map_source, sample_root=sample_root)
    regen_target = output_dir / "regen.txt"
    regen_target.write_text(regen_text, encoding="utf-8")
    result.files_written.append("regen.txt")

    stone_text, stone_source = build_stone_text(map_source, sample_root=sample_root)
    stone_target = output_dir / "stone.txt"
    stone_target.write_text(stone_text, encoding="utf-8")
    result.files_written.append("stone.txt")

    town_text, town_source = build_town_text(map_source, sample_root=sample_root)
    town_target = output_dir / "Town.txt"
    town_target.write_text(town_text, encoding="utf-8")
    result.files_written.append("Town.txt")

    sungma_source = _find_optional_text_file(map_source, sample_root, "sungma_attr.txt")
    sungma_source_label: str | None = None
    if sungma_source is not None:
        sungma_target = output_dir / "sungma_attr.txt"
        sungma_target.write_text(sungma_source.read_text(encoding="utf-8"), encoding="utf-8")
        result.files_written.append("sungma_attr.txt")
        sungma_source_label = _format_source_label(sungma_source, map_source, sample_root)

    server_attr_status = "SKIPPED"
    server_attr_error: str | None = None
    server_attr_target = output_dir / "server_attr"
    if is_lzo_backend_available() and map_source.attr_files:
        try:
            export_server_attr(map_source, server_attr_target)
            result.files_written.append("server_attr")
            server_attr_status = "EXPORTED"
        except ValueError as exc:
            server_attr_status = "SKIPPED_ERROR"
            server_attr_error = str(exc)
            result.warnings.append(f"server_attr uretilmedi: {exc}")
    elif not map_source.attr_files:
        server_attr_status = "SKIPPED_NO_ATTR"
        result.warnings.append("server_attr uretilmedi: attr.atr dosyasi bulunamadi")
    else:
        server_attr_status = "SKIPPED_NO_LZO"
        result.warnings.append("server_attr uretilmedi: LZO backend bulunamadi")

    server_attr_compare = None
    if server_attr_status == "EXPORTED":
        server_attr_compare = _compare_generated_server_attr(map_source, server_attr_target, sample_root)

    report = {
        "map_name": map_source.name,
        "source_path": str(map_source.path),
        "setting_path": str(map_source.setting_path),
        "parent_map_name": map_source.parent_map_name,
        "attr_source_map_name": map_source.attr_source_map_name,
        "attr_source_path": str(map_source.attr_source_path) if map_source.attr_source_path else None,
        "area_directory_count": len(map_source.area_directories),
        "attr_file_count": len(map_source.attr_files),
        "warnings": list(result.warnings),
        "boss_source": boss_source,
        "npc_source": npc_source,
        "regen_source": regen_source,
        "stone_source": stone_source,
        "town_source": town_source,
        "sungma_attr_source": sungma_source_label,
        "server_attr_status": server_attr_status,
        "server_attr_error": server_attr_error,
        "server_attr_compare": server_attr_compare,
    }
    result.report = report

    return result


def build_generation_summary(
    results: List[MapGenerationResult],
    requested_map_names: list[str] | None = None,
    missing_requested_maps: list[str] | None = None,
) -> dict:
    server_attr_status_counts: dict[str, int] = {}
    boss_source_counts: dict[str, int] = {}
    npc_source_counts: dict[str, int] = {}
    regen_source_counts: dict[str, int] = {}
    stone_source_counts: dict[str, int] = {}
    town_source_counts: dict[str, int] = {}
    maps: list[dict] = []

    for result in results:
        report = result.report
        server_attr_status = report["server_attr_status"]
        server_attr_status_counts[server_attr_status] = (
            server_attr_status_counts.get(server_attr_status, 0) + 1
        )
        for source_key, counter in (
            ("boss_source", boss_source_counts),
            ("npc_source", npc_source_counts),
            ("regen_source", regen_source_counts),
            ("stone_source", stone_source_counts),
            ("town_source", town_source_counts),
        ):
            source_value = report[source_key]
            counter[source_value] = counter.get(source_value, 0) + 1
        maps.append(
            {
                "map_name": result.map_name,
                "output_path": str(result.output_path),
                "files_written": list(result.files_written),
                "warnings": list(result.warnings),
                "attr_source_map_name": report["attr_source_map_name"],
                "attr_source_path": report["attr_source_path"],
                "boss_source": report["boss_source"],
                "npc_source": report["npc_source"],
                "regen_source": report["regen_source"],
                "stone_source": report["stone_source"],
                "town_source": report["town_source"],
                "sungma_attr_source": report["sungma_attr_source"],
                "server_attr_status": report["server_attr_status"],
                "server_attr_error": report["server_attr_error"],
                "server_attr_compare": report["server_attr_compare"],
            }
        )

    return {
        "requested_map_names": list(requested_map_names or []),
        "requested_map_count": len(requested_map_names or []),
        "missing_requested_maps": list(missing_requested_maps or []),
        "missing_requested_map_count": len(missing_requested_maps or []),
        "map_count": len(results),
        "generated_map_count": len(results),
        "server_attr_status_counts": server_attr_status_counts,
        "boss_source_counts": boss_source_counts,
        "npc_source_counts": npc_source_counts,
        "regen_source_counts": regen_source_counts,
        "stone_source_counts": stone_source_counts,
        "town_source_counts": town_source_counts,
        "maps": maps,
    }


def write_generation_summary(
    results: List[MapGenerationResult],
    output_file: str | Path,
    requested_map_names: list[str] | None = None,
    missing_requested_maps: list[str] | None = None,
) -> Path:
    summary = build_generation_summary(
        results,
        requested_map_names=requested_map_names,
        missing_requested_maps=missing_requested_maps,
    )
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return output_path


def _find_optional_text_file(
    map_source: MapSource,
    sample_root: str | Path | None,
    file_name: str,
) -> Path | None:
    candidates = [map_source.path / file_name]
    if map_source.attr_source_path is not None:
        candidates.append(map_source.attr_source_path / file_name)
    if sample_root is not None:
        sample_root_path = Path(sample_root)
        candidates.append(sample_root_path / map_source.name / file_name)
        if map_source.attr_source_map_name:
            candidates.append(sample_root_path / map_source.attr_source_map_name / file_name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _format_source_label(
    source_path: Path,
    map_source: MapSource,
    sample_root: str | Path | None,
) -> str:
    if source_path.is_relative_to(map_source.path):
        return f"source:{map_source.name}"
    if map_source.attr_source_path is not None and source_path.is_relative_to(map_source.attr_source_path):
        return f"attr_source:{map_source.attr_source_map_name or map_source.attr_source_path.name}"
    if sample_root is not None:
        try:
            relative = source_path.relative_to(Path(sample_root))
            return f"sample:{relative.parts[0]}"
        except ValueError:
            pass
    return str(source_path)


def _compare_generated_server_attr(
    map_source: MapSource,
    generated_path: Path,
    sample_root: str | Path | None,
) -> dict:
    generated = analyze_server_attr_file(generated_path)
    official_candidates: list[Path] = []
    if (map_source.path / "server_attr").exists():
        official_candidates.append(map_source.path / "server_attr")
    if map_source.attr_source_path is not None and (map_source.attr_source_path / "server_attr").exists():
        official_candidates.append(map_source.attr_source_path / "server_attr")
    if sample_root is not None:
        sample_root_path = Path(sample_root)
        if (sample_root_path / map_source.name / "server_attr").exists():
            official_candidates.append(sample_root_path / map_source.name / "server_attr")
        if map_source.attr_source_map_name and (
            sample_root_path / map_source.attr_source_map_name / "server_attr"
        ).exists():
            official_candidates.append(sample_root_path / map_source.attr_source_map_name / "server_attr")

    unique_candidates: list[Path] = []
    seen = set()
    for candidate in official_candidates:
        key = str(candidate.resolve())
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    comparisons = []
    for official_path in unique_candidates:
        official = analyze_server_attr_file(official_path)
        raw_compare = _compare_server_attr_raw_blocks(generated_path, official_path)
        comparisons.append(
            {
                "official_path": str(official_path),
                "official_size": official.size,
                "generated_size": generated.size,
                "size_matches": official.size == generated.size,
                "official_grid": [official.sectree_width, official.sectree_height],
                "generated_grid": [generated.sectree_width, generated.sectree_height],
                "grid_matches": (
                    official.sectree_width == generated.sectree_width
                    and official.sectree_height == generated.sectree_height
                ),
                "official_block_count": official.block_count,
                "generated_block_count": generated.block_count,
                "block_count_matches": official.block_count == generated.block_count,
                "raw_blocks_match": raw_compare["raw_blocks_match"],
                "raw_block_mismatch_count": raw_compare["raw_block_mismatch_count"],
                "raw_compare_error": raw_compare["error"],
            }
        )

    return {
        "generated_path": str(generated_path),
        "generated_size": generated.size,
        "generated_grid": [generated.sectree_width, generated.sectree_height],
        "generated_block_count": generated.block_count,
        "official_comparisons": comparisons,
    }


def _compare_server_attr_raw_blocks(generated_path: Path, official_path: Path) -> dict:
    if lzo is None:
        return {
            "raw_blocks_match": None,
            "raw_block_mismatch_count": None,
            "error": "LZO backend bulunamadi",
        }

    try:
        generated_hashes = _server_attr_raw_block_hashes(generated_path)
        official_hashes = _server_attr_raw_block_hashes(official_path)
    except Exception as exc:
        return {
            "raw_blocks_match": None,
            "raw_block_mismatch_count": None,
            "error": str(exc),
        }

    mismatch_count = 0
    for index in range(max(len(generated_hashes), len(official_hashes))):
        generated_hash = generated_hashes[index] if index < len(generated_hashes) else None
        official_hash = official_hashes[index] if index < len(official_hashes) else None
        if generated_hash != official_hash:
            mismatch_count += 1

    return {
        "raw_blocks_match": mismatch_count == 0,
        "raw_block_mismatch_count": mismatch_count,
        "error": None,
    }


def _server_attr_raw_block_hashes(path: Path) -> list[str]:
    data = path.read_bytes()
    offset = 8
    hashes: list[str] = []
    while offset < len(data):
        compressed_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        payload = data[offset:offset + compressed_size]
        offset += compressed_size
        raw = lzo.decompress(payload, False, 128 * 128 * 4)
        hashes.append(hashlib.md5(raw).hexdigest())
    return hashes
