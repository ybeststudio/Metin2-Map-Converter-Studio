from __future__ import annotations

from pathlib import Path

from app.core.map_reader import MapSource
from app.core.sample_text_resolver import resolve_sample_text


def build_town_text(
    map_source: MapSource,
    sample_root: str | Path | None = None,
) -> tuple[str, str]:
    sample_text, sample_source = resolve_sample_text(
        map_source,
        "Town.txt",
        sample_root=sample_root,
    )
    if sample_text is not None and sample_source is not None:
        return _normalize_town_text(sample_text.strip()), sample_source

    width = map_source.setting.width * 256
    height = map_source.setting.height * 256
    center_x = max(1, width // 2)
    center_y = max(1, height // 2)
    return f"{center_x}\t{center_y}\n", "setting_center_fallback"


def _normalize_town_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            lines.append(f"{parts[0]}\t{parts[1]}")
        else:
            lines.append(line)
    return "\n".join(lines).strip() + "\n"
