"""Validate desktop icon assets before packaging."""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_ICON = ROOT / "src-tauri" / "icons" / "icon.ico"
FLET_ICON = ROOT / "assets" / "icon.png"
REQUIRED_WINDOWS_SIZES = {
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
}


def read_ico_sizes(path: Path) -> list[tuple[int, int]]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"ICO file is too small: {path}")

    reserved, resource_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or resource_type != 1 or count == 0:
        raise ValueError(f"invalid ICO header: {path}")
    if len(data) < 6 + count * 16:
        raise ValueError(f"ICO directory is truncated: {path}")

    sizes = []
    for index in range(count):
        width, height, _, _, _, _, payload_size, payload_offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + index * 16
        )
        if payload_offset + payload_size > len(data):
            raise ValueError(f"ICO payload is truncated: {path}")
        sizes.append((width or 256, height or 256))
    return sizes


def read_png_info(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    if len(data) < 26 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"invalid PNG header: {path}")
    width, height = struct.unpack_from(">II", data, 16)
    return width, height, data[25]


def validate() -> tuple[list[tuple[int, int]], tuple[int, int, int]]:
    ico_sizes = read_ico_sizes(WINDOWS_ICON)
    missing_sizes = REQUIRED_WINDOWS_SIZES - set(ico_sizes)
    if missing_sizes:
        raise ValueError(f"Windows ICO is missing sizes: {sorted(missing_sizes)}")
    if ico_sizes[0] != (32, 32):
        raise ValueError(f"first Windows ICO layer must be 32x32 for Tauri: {ico_sizes[0]}")

    png_info = read_png_info(FLET_ICON)
    width, height, _ = png_info
    if width < 512 or height < 512:
        raise ValueError(f"Flet icon must be at least 512x512: {width}x{height}")
    return ico_sizes, png_info


def main() -> int:
    try:
        ico_sizes, (width, height, _) = validate()
    except (OSError, ValueError) as exc:
        print(f"Desktop icon validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Windows ICO: {', '.join(f'{w}x{h}' for w, h in ico_sizes)}")
    print(f"Flet icon: {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
