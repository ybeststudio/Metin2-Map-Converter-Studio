from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

from app.core.map_reader import MapSource
from app.core.raw_sectree_block_packer import build_raw_sectree_dword_blocks_with_profile
from app.core.server_attr_analyzer import (
    RAW_BYTES_PER_SECTREE,
    analyze_server_attr_file,
    find_matching_server_attr_sample,
    is_lzo_backend_available,
)

try:
    import lzo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    lzo = None


def build_server_attr_block_diff_report(
    map_source: MapSource,
    sample_root: str | Path,
    mapping_profile: str = "exe_compat_v2",
    block_limit: int = 8,
) -> dict:
    if lzo is None:
        raise RuntimeError("LZO backend bulunamadi. `python-lzo==1.15` gerekli.")

    sample_path = find_matching_server_attr_sample(map_source.name, sample_root)
    if sample_path is None:
        raise ValueError(f"Ornek server_attr bulunamadi: {map_source.name}")

    sample = analyze_server_attr_file(sample_path)
    generated_blocks = build_raw_sectree_dword_blocks_with_profile(
        map_source,
        mapping_profile=mapping_profile,
    )
    sample_blocks = _read_decompressed_dword_blocks(sample_path, block_limit=block_limit)

    compared_blocks: list[dict] = []
    mismatch_counter: Counter[int] = Counter()

    for sample_block in sample_blocks:
        index = sample_block["block_index"]
        generated = generated_blocks[index]
        sample_dwords = sample_block["dwords"]
        mismatch_positions = [
            pos for pos, (left, right) in enumerate(zip(generated, sample_dwords)) if left != right
        ]
        mismatch_count = len(mismatch_positions)

        for pos in mismatch_positions[:256]:
            mismatch_counter[generated[pos]] += 1

        compared_blocks.append(
            {
                "block_index": index,
                "compressed_size": sample_block["compressed_size"],
                "mismatch_count": mismatch_count,
                "match_ratio": _ratio(len(generated) - mismatch_count, len(generated)),
                "generated_first_dwords": [f"0x{value:08X}" for value in generated[:8]],
                "sample_first_dwords": [f"0x{value:08X}" for value in sample_dwords[:8]],
                "first_mismatch_positions": mismatch_positions[:16],
            }
        )

    return {
        "map_name": map_source.name,
        "mapping_profile": mapping_profile,
        "lzo_backend_available": is_lzo_backend_available(),
        "sample_path": str(sample.path),
        "sample_block_count": sample.block_count,
        "generated_block_count": len(generated_blocks),
        "validated_block_count": len(compared_blocks),
        "compared_blocks": compared_blocks,
        "top_generated_mismatch_dwords": [
            {
                "dword": value,
                "hex": f"0x{value:08X}",
                "count": count,
            }
            for value, count in mismatch_counter.most_common(12)
        ],
    }


def write_server_attr_block_diff_report(
    map_source: MapSource,
    sample_root: str | Path,
    output_file: str | Path,
    mapping_profile: str = "exe_compat_v2",
    block_limit: int = 8,
) -> Path:
    report = build_server_attr_block_diff_report(
        map_source,
        sample_root=sample_root,
        mapping_profile=mapping_profile,
        block_limit=block_limit,
    )
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def build_batch_server_attr_block_diff_summary(
    map_sources: list[MapSource],
    sample_root: str | Path,
    mapping_profile: str = "exe_compat_v2",
    block_limit: int = 8,
) -> dict:
    if lzo is None:
        raise RuntimeError("LZO backend bulunamadi. `python-lzo==1.15` gerekli.")

    sample_root_path = Path(sample_root)
    maps: list[dict] = []
    skipped_maps: list[dict] = []
    mismatch_counter: Counter[int] = Counter()
    fully_matching_map_count = 0
    total_compared_blocks = 0
    total_mismatch_count = 0

    for map_source in map_sources:
        sample_path = find_matching_server_attr_sample(map_source.name, sample_root_path)
        if sample_path is None:
            continue

        try:
            report = build_server_attr_block_diff_report(
                map_source,
                sample_root=sample_root_path,
                mapping_profile=mapping_profile,
                block_limit=block_limit,
            )
        except ValueError as exc:
            skipped_maps.append(
                {
                    "map_name": map_source.name,
                    "reason": str(exc),
                }
            )
            continue

        mismatch_block_count = sum(
            1 for block in report["compared_blocks"] if block["mismatch_count"] > 0
        )
        map_mismatch_count = sum(
            block["mismatch_count"] for block in report["compared_blocks"]
        )
        worst_block_match_ratio = min(
            (block["match_ratio"] for block in report["compared_blocks"]),
            default=1.0,
        )

        if mismatch_block_count == 0:
            fully_matching_map_count += 1

        total_compared_blocks += report["validated_block_count"]
        total_mismatch_count += map_mismatch_count

        for item in report["top_generated_mismatch_dwords"]:
            mismatch_counter[item["dword"]] += item["count"]

        maps.append(
            {
                "map_name": report["map_name"],
                "sample_block_count": report["sample_block_count"],
                "generated_block_count": report["generated_block_count"],
                "validated_block_count": report["validated_block_count"],
                "mismatch_block_count": mismatch_block_count,
                "total_mismatch_count": map_mismatch_count,
                "all_blocks_match": mismatch_block_count == 0,
                "worst_block_match_ratio": worst_block_match_ratio,
                "sample_path": report["sample_path"],
            }
        )

    return {
        "sample_root": str(sample_root_path),
        "mapping_profile": mapping_profile,
        "block_limit": block_limit,
        "lzo_backend_available": is_lzo_backend_available(),
        "map_count": len(maps),
        "fully_matching_map_count": fully_matching_map_count,
        "total_compared_blocks": total_compared_blocks,
        "total_mismatch_count": total_mismatch_count,
        "top_generated_mismatch_dwords": [
            {
                "dword": value,
                "hex": f"0x{value:08X}",
                "count": count,
            }
            for value, count in mismatch_counter.most_common(12)
        ],
        "skipped_maps": skipped_maps,
        "maps": maps,
    }


def write_batch_server_attr_block_diff_summary(
    map_sources: list[MapSource],
    sample_root: str | Path,
    output_file: str | Path,
    mapping_profile: str = "exe_compat_v2",
    block_limit: int = 8,
) -> Path:
    summary = build_batch_server_attr_block_diff_summary(
        map_sources,
        sample_root=sample_root,
        mapping_profile=mapping_profile,
        block_limit=block_limit,
    )
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return target


def _read_decompressed_dword_blocks(
    file_path: str | Path,
    block_limit: int,
) -> list[dict]:
    path = Path(file_path)
    data = path.read_bytes()
    offset = 8
    block_index = 0
    blocks: list[dict] = []

    while offset < len(data) and block_index < block_limit:
        compressed_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        payload = data[offset:offset + compressed_size]
        offset += compressed_size
        raw = lzo.decompress(payload, False, RAW_BYTES_PER_SECTREE)
        dwords = list(struct.unpack(f"<{RAW_BYTES_PER_SECTREE // 4}I", raw))
        blocks.append(
            {
                "block_index": block_index,
                "compressed_size": compressed_size,
                "dwords": dwords,
            }
        )
        block_index += 1

    return blocks


def _ratio(left: int, right: int) -> float:
    if right == 0:
        return 0.0
    return round(left / right, 6)
