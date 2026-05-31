from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.bulk_generator import (
    build_generation_summary,
    generate_map_output,
    write_generation_summary,
)
from app.core.map_reader import resolve_map_source_by_name


@dataclass(slots=True)
class GenerationWorkflowResult:
    requested_map_names: list[str]
    missing_requested_maps: list[str]
    generated_map_count: int
    report_path: Path
    output_root: Path
    summary: dict


def run_selected_generation(
    source_root: str | Path,
    output_root: str | Path,
    requested_map_names: list[str],
    sample_root: str | Path | None,
    report_file: str | Path,
) -> GenerationWorkflowResult:
    if not requested_map_names:
        raise ValueError("En az bir map adi verilmeli")

    source_root_path = Path(source_root)
    output_root_path = Path(output_root)
    output_root_path.mkdir(parents=True, exist_ok=True)

    results = []
    missing_requested_maps: list[str] = []
    for map_name in requested_map_names:
        selected = resolve_map_source_by_name(source_root_path, map_name)
        if selected is None:
            missing_requested_maps.append(map_name)
            continue
        results.append(
            generate_map_output(
                selected,
                output_root_path,
                sample_root=sample_root,
            )
        )

    report_path = write_generation_summary(
        results,
        report_file,
        requested_map_names=requested_map_names,
        missing_requested_maps=missing_requested_maps,
    )
    summary = build_generation_summary(
        results,
        requested_map_names=requested_map_names,
        missing_requested_maps=missing_requested_maps,
    )
    return GenerationWorkflowResult(
        requested_map_names=list(requested_map_names),
        missing_requested_maps=missing_requested_maps,
        generated_map_count=summary["generated_map_count"],
        report_path=report_path,
        output_root=output_root_path,
        summary=summary,
    )
