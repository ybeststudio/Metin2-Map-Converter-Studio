from __future__ import annotations

from pathlib import Path

from app.core.map_reader import MapSource
from app.core.sample_text_resolver import resolve_sample_text


def build_boss_text(
    map_source: MapSource,
    sample_root: str | Path | None = None,
) -> tuple[str, str]:
    sample_text, sample_source = resolve_sample_text(
        map_source,
        "boss.txt",
        sample_root=sample_root,
    )
    if sample_text is not None and sample_source is not None:
        return _normalize_boss_text(sample_text), sample_source
    return "", "empty_fallback"


def _normalize_boss_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        parts = line.split()
        lines.append("\t".join(parts))
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
