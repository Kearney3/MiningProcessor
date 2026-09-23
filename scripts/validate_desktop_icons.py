"""Validate desktop icon assets before packaging."""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS_ICON = ROOT / "src-tauri" / "icons" / "icon.ico"
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


def validate() -> list[tuple[int, int]]:
    ico_sizes = read_ico_sizes(WINDOWS_ICON)
    missing_sizes = REQUIRED_WINDOWS_SIZES - set(ico_sizes)
    if missing_sizes:
        raise ValueError(f"Windows ICO is missing sizes: {sorted(missing_sizes)}")
    if ico_sizes[0] != (32, 32):
        raise ValueError(f"first Windows ICO layer must be 32x32 for Tauri: {ico_sizes[0]}")

    return ico_sizes


def main() -> int:
    try:
        ico_sizes = validate()
    except (OSError, ValueError) as exc:
        print(f"Desktop icon validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Windows ICO: {', '.join(f'{w}x{h}' for w, h in ico_sizes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
