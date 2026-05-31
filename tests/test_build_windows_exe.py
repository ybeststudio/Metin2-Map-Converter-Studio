from __future__ import annotations

from pathlib import Path

from scripts.build_windows_exe import (
    build_pyinstaller_args,
    build_version_file_contents,
    get_default_icon_path,
    normalize_version,
)


def test_build_pyinstaller_args_defaults_to_onedir_and_clean() -> None:
    project_root = Path(r"D:\ymir work\MapConverter")

    args = build_pyinstaller_args(
        project_root,
        onefile=False,
        clean=True,
    )

    assert str(project_root / "src" / "app" / "launch_gui.py") == args[0]
    assert "--onedir" in args
    assert "--onefile" not in args
    assert "--clean" in args
    assert "lzo" in args
    assert "--version-file" in args


def test_build_pyinstaller_args_supports_onefile_without_clean() -> None:
    project_root = Path(r"D:\ymir work\MapConverter")
    icon_path = project_root / "assets" / "app.ico"

    args = build_pyinstaller_args(
        project_root,
        onefile=True,
        clean=False,
        app_name="CustomGui",
        version="1.2.3",
        icon_path=icon_path,
    )

    assert "--onefile" in args
    assert "--onedir" not in args
    assert "--clean" not in args
    assert "CustomGui" in args
    assert "--icon" in args
    assert str(icon_path) in args


def test_normalize_version_pads_missing_parts() -> None:
    assert normalize_version("1.2") == (1, 2, 0, 0)


def test_build_version_file_contents_includes_version_metadata() -> None:
    contents = build_version_file_contents("MapConverterGui", "1.2.3")

    assert "StringStruct('FileVersion', '1.2.3.0')" in contents
    assert "StringStruct('OriginalFilename', 'MapConverterGui.exe')" in contents


def test_get_default_icon_path_returns_assets_icon_when_present(tmp_path) -> None:
    icon_path = tmp_path / "assets" / "app.ico"
    icon_path.parent.mkdir(parents=True)
    icon_path.write_bytes(b"ico")

    assert get_default_icon_path(tmp_path) == icon_path
