from __future__ import annotations

import importlib.util
from pathlib import Path


SRC_APP_ROOT = Path(__file__).resolve().parent.parent / "src" / "app"
__path__ = [str(SRC_APP_ROOT)]

_src_init_spec = importlib.util.spec_from_file_location(
    "_map_converter_src_app",
    SRC_APP_ROOT / "__init__.py",
)
if _src_init_spec is None or _src_init_spec.loader is None:  # pragma: no cover
    raise ImportError(f"src app paketi yuklenemedi: {SRC_APP_ROOT}")

_src_init_module = importlib.util.module_from_spec(_src_init_spec)
_src_init_spec.loader.exec_module(_src_init_module)

__version__ = _src_init_module.__version__
