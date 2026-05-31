from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for import_path in (PROJECT_ROOT, SRC_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app import __version__


DEFAULT_APP_NAME = "MapConverterGui"


def get_default_icon_path(project_root: Path) -> Path | None:
    icon_path = project_root / "assets" / "app.ico"
    if icon_path.exists():
        return icon_path
    return None


def build_pyinstaller_args(
    project_root: Path,
    *,
    onefile: bool,
    clean: bool,
    app_name: str = DEFAULT_APP_NAME,
    version: str = __version__,
    icon_path: Path | None = None,
) -> list[str]:
    entry_script = project_root / "src" / "app" / "launch_gui.py"
    dist_path = project_root / "dist"
    work_path = project_root / "build" / "pyinstaller"
    spec_path = project_root / "build" / "spec"
    version_file = write_version_file(project_root, app_name=app_name, version=version)
    resolved_icon_path = icon_path or get_default_icon_path(project_root)

    args = [
        str(entry_script),
        "--name",
        app_name,
        "--noconfirm",
        "--windowed",
        "--paths",
        str(project_root / "src"),
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
        "--hidden-import",
        "lzo",
        "--version-file",
        str(version_file),
    ]
    if resolved_icon_path is not None:
        args.extend(["--icon", str(resolved_icon_path)])
    args.append("--onefile" if onefile else "--onedir")
    if clean:
        args.append("--clean")
    return args


def build_version_file_contents(app_name: str, version: str) -> str:
    major, minor, patch, build = normalize_version(version)
    version_text = f"{major}.{minor}.{patch}.{build}"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [
        StringStruct('CompanyName', 'BestStudio'),
        StringStruct('FileDescription', '{app_name}'),
        StringStruct('FileVersion', '{version_text}'),
        StringStruct('InternalName', '{app_name}'),
        StringStruct('OriginalFilename', '{app_name}.exe'),
        StringStruct('ProductName', 'Metin2 Map Converter'),
        StringStruct('ProductVersion', '{version_text}')
        ])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""


def normalize_version(version: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in version.split(".") if part.strip()]
    if not parts:
        raise ValueError("Version bos olamaz.")
    if len(parts) > 4:
        raise ValueError("Version en fazla 4 bolum icerebilir.")

    normalized: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError("Version sadece sayisal bolumler icermelidir.")
        normalized.append(int(part))

    while len(normalized) < 4:
        normalized.append(0)
    return normalized[0], normalized[1], normalized[2], normalized[3]


def write_version_file(project_root: Path, *, app_name: str, version: str) -> Path:
    version_dir = project_root / "build" / "versioninfo"
    version_dir.mkdir(parents=True, exist_ok=True)
    version_file = version_dir / f"{app_name}.version.txt"
    version_file.write_text(
        build_version_file_contents(app_name, version),
        encoding="utf-8",
    )
    return version_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Metin2 Map Converter GUI icin Windows exe paketi uretir.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        default=True,
        help="Tek exe cikisi uret. Varsayilan olarak aciktir.",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Tek exe yerine klasorlu PyInstaller cikisi uret.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="PyInstaller build cache temizligini kapat.",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_APP_NAME,
        help="Exe dosyasi icin kullanilacak uygulama adi.",
    )
    parser.add_argument(
        "--version",
        default=__version__,
        help="Exe metadata icin kullanilacak surum numarasi. Ornek: 1.2.0",
    )
    parser.add_argument(
        "--icon",
        help="Opsiyonel .ico dosyasi yolu.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = PROJECT_ROOT
    icon_path = Path(args.icon).resolve() if args.icon else get_default_icon_path(project_root)
    if icon_path is not None and not icon_path.exists():
        raise SystemExit(f"Ikon dosyasi bulunamadi: {icon_path}")

    try:
        from PyInstaller.__main__ import run as pyinstaller_run
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime usage
        raise SystemExit(
            "PyInstaller kurulu degil. Once `python -m pip install -r requirements.txt` calistir."
        ) from exc

    pyinstaller_args = build_pyinstaller_args(
        project_root,
        onefile=not args.onedir,
        clean=not args.no_clean,
        app_name=args.name,
        version=args.version,
        icon_path=icon_path,
    )
    pyinstaller_run(pyinstaller_args)
    publish_exe_to_bin(project_root, app_name=args.name, onefile=args.onefile)
    return 0


def publish_exe_to_bin(project_root: Path, *, app_name: str, onefile: bool) -> Path:
    if onefile:
        source = project_root / "dist" / f"{app_name}.exe"
    else:
        source = project_root / "dist" / app_name / f"{app_name}.exe"
    if not source.exists():
        raise SystemExit(f"Build exe bulunamadi: {source}")

    bin_dir = project_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / f"{app_name}.exe"
    shutil.copy2(source, target)
    return target


if __name__ == "__main__":
    raise SystemExit(main())
