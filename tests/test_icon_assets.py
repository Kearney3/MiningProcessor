"""Regression checks for desktop application icon assets."""

import importlib.util
from pathlib import Path

from PIL import Image

from scripts.validate_desktop_icons import (
    FLET_ICON,
    REQUIRED_WINDOWS_SIZES,
    WINDOWS_ICON,
    read_ico_sizes,
    read_png_info,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_icon_generator():
    path = ROOT / "src-tauri" / "icons" / "generate_icon.py"
    spec = importlib.util.spec_from_file_location("icon_generator", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_icon_contains_high_resolution_layers() -> None:
    sizes = read_ico_sizes(WINDOWS_ICON)

    assert REQUIRED_WINDOWS_SIZES <= set(sizes)
    # Tauri uses the first ICO entry for the default Windows window icon.
    assert sizes[0] == (32, 32)


def test_flet_default_icon_is_high_resolution_png() -> None:
    width, height, _ = read_png_info(FLET_ICON)

    assert (width, height) == (512, 512)


def test_icon_generator_preserves_tauri_first_layer_order(tmp_path: Path) -> None:
    generator = _load_icon_generator()
    output = tmp_path / "icon.ico"

    generator._write_ico(Image.new("RGBA", (512, 512), "#123456"), output)

    assert read_ico_sizes(output) == generator.ICO_SIZES
