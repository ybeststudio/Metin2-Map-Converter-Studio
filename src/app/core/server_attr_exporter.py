from __future__ import annotations

import json
import struct
from pathlib import Path

from app.core.coordinate import geometry_from_setting
from app.core.map_reader import MapSource
from app.core.raw_sectree_block_packer import (
    RAW_BYTES_PER_SECTREE,
    pack_raw_sectree_block_bytes,
    pack_raw_sectree_block_bytes_with_profile,
)
from app.core.server_attr_analyzer import analyze_server_attr_file, find_matching_server_attr_sample

try:
    import lzo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - tested through backend availability checks
    lzo = None


def is_lzo_backend_available() -> bool:
    return lzo is not None


def export_server_attr(
    map_source: MapSource,
    output_file: str | Path,
    mapping_profile: str = "exe_compat_v2",
) -> Path:
    _require_lzo_backend()
    geometry = geometry_from_setting(map_source.setting)
    if mapping_profile == "candidate_v1":
        block_payloads = pack_raw_sectree_block_bytes(map_source)
    else:
        block_payloads = pack_raw_sectree_block_bytes_with_profile(
            map_source,
            mapping_profile=mapping_profile,
        )
    compressed_blocks = [_compress_block(payload) for payload in block_payloads]

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as handle:
        handle.write(struct.pack("<II", geometry.sectree_width, geometry.sectree_height))
        for block in compressed_blocks:
            handle.write(struct.pack("<I", len(block)))
            handle.write(block)

    return output_path


def build_server_attr_export_report(
    map_source: MapSource,
    output_file: str | Path,
    sample_root: str | Path | None = None,
    mapping_profile: str = "exe_compat_v2",
) -> dict:
    geometry = geometry_from_setting(map_source.setting)
    output_path = export_server_attr(
        map_source,
        output_file,
        mapping_profile=mapping_profile,
    )
    exported = analyze_server_attr_file(output_path)

    report = {
        "map_name": map_source.name,
        "output_file": str(output_path),
        "lzo_backend_available": is_lzo_backend_available(),
        "mapping_profile": mapping_profile,
        "sectree_grid": {
            "width": geometry.sectree_width,
            "height": geometry.sectree_height,
        },
        "expected_block_count": geometry.sectree_width * geometry.sectree_height,
        "raw_bytes_per_block": RAW_BYTES_PER_SECTREE,
        "exported_server_attr": {
            "size": exported.size,
            "sectree_width": exported.sectree_width,
            "sectree_height": exported.sectree_height,
            "block_count": exported.block_count,
            "first_block_sizes": exported.first_block_sizes,
            "block_size_stats": exported.block_size_stats,
        },
        "validation": {
            "header_matches": (
                exported.sectree_width == geometry.sectree_width
                and exported.sectree_height == geometry.sectree_height
            ),
            "block_count_matches": exported.block_count
            == geometry.sectree_width * geometry.sectree_height,
        },
    }

    if sample_root is not None:
        sample_path = find_matching_server_attr_sample(map_source.name, sample_root)
        if sample_path is not None:
            sample = analyze_server_attr_file(sample_path)
            report["sample_comparison"] = {
                "sample_path": str(sample.path),
                "sample_size": sample.size,
                "sample_block_count": sample.block_count,
                "sample_first_block_sizes": sample.first_block_sizes,
                "sample_block_size_stats": sample.block_size_stats,
                "size_delta": exported.size - sample.size,
                "first_block_size_delta": [
                    current - reference
                    for current, reference in zip(
                        exported.first_block_sizes,
                        sample.first_block_sizes,
                    )
                ],
            }

    return report


def write_server_attr_export_report(
    map_source: MapSource,
    output_file: str | Path,
    report_file: str | Path,
    sample_root: str | Path | None = None,
    mapping_profile: str = "exe_compat_v2",
) -> Path:
    report = build_server_attr_export_report(
        map_source,
        output_file=output_file,
        sample_root=sample_root,
        mapping_profile=mapping_profile,
    )
    report_path = Path(report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return report_path


def export_server_attr_batch(
    map_sources: list[MapSource],
    output_root: str | Path,
    sample_root: str | Path | None = None,
    mapping_profile: str = "exe_compat_v2",
) -> dict:
    _require_lzo_backend()
    output_root_path = Path(output_root)
    output_root_path.mkdir(parents=True, exist_ok=True)
    maps: list[dict] = []
    skipped_maps: list[dict] = []

    for map_source in map_sources:
        if not map_source.attr_files:
            continue
        try:
            output_file = output_root_path / map_source.name / "server_attr"
            report = build_server_attr_export_report(
                map_source,
                output_file=output_file,
                sample_root=sample_root,
                mapping_profile=mapping_profile,
            )
        except ValueError as exc:
            skipped_maps.append(
                {
                    "map_name": map_source.name,
                    "reason": str(exc),
                }
            )
            continue

        maps.append(
            {
                "map_name": report["map_name"],
                "output_file": report["output_file"],
                "size": report["exported_server_attr"]["size"],
                "block_count": report["exported_server_attr"]["block_count"],
                "block_size_stats": report["exported_server_attr"]["block_size_stats"],
                "validation": report["validation"],
            }
        )

    return {
        "output_root": str(output_root_path),
        "mapping_profile": mapping_profile,
        "map_count": len(maps),
        "skipped_map_count": len(skipped_maps),
        "skipped_maps": skipped_maps,
        "maps": maps,
    }


def write_server_attr_batch_summary(
    map_sources: list[MapSource],
    output_root: str | Path,
    report_file: str | Path,
    sample_root: str | Path | None = None,
    summary: dict | None = None,
    mapping_profile: str = "exe_compat_v2",
) -> Path:
    if summary is None:
        summary = export_server_attr_batch(
            map_sources,
            output_root=output_root,
            sample_root=sample_root,
            mapping_profile=mapping_profile,
        )
    report_path = Path(report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return report_path


def _compress_block(raw_payload: bytes) -> bytes:
    _require_lzo_backend()
    compressed = lzo.compress(raw_payload, 1, False)
    verified = lzo.decompress(compressed, False, len(raw_payload))
    if verified != raw_payload:
        raise ValueError("LZO roundtrip dogrulamasi basarisiz")
    return compressed


def _require_lzo_backend() -> None:
    if lzo is None:
        raise RuntimeError(
            "LZO backend bulunamadi. `python -m pip install python-lzo==1.15` calistirin."
        )
