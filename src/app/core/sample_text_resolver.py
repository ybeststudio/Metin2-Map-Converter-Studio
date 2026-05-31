from __future__ import annotations

from pathlib import Path

from app.core.map_reader import MapSource


def resolve_sample_text(
    map_source: MapSource,
    file_name: str,
    sample_root: str | Path | None = None,
) -> tuple[str | None, str | None]:
    root = Path(sample_root) if sample_root is not None else Path.cwd() / "output ornekleri"

    for candidate_name in iter_sample_candidates(map_source):
        sample_path = root / candidate_name / file_name
        if sample_path.exists():
            return _read_text_with_fallback(sample_path), f"sample:{candidate_name}"
    return None, None


def iter_sample_candidates(map_source: MapSource) -> list[str]:
    candidates: list[str] = []
    for candidate in (
        map_source.name,
        map_source.parent_map_name,
        map_source.path.name,
        strip_pass_suffix(map_source.name),
        strip_pass_suffix(map_source.path.name),
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def strip_pass_suffix(map_name: str | None) -> str | None:
    if not map_name:
        return None
    if map_name.endswith("_pass"):
        return map_name[:-5]
    return None


def _read_text_with_fallback(file_path: Path) -> str:
    for encoding in ("utf-8", "cp949", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")
