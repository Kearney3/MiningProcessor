"""从 assets/logo.png 生成各平台应用图标。"""
from pathlib import Path
import subprocess
import shutil
from PIL import Image

ICONS_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ICONS_DIR.parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

SZ = 512
SOURCE_LOGO = ASSETS_DIR / "logo.png"


def draw_icon(size: int) -> Image.Image:
    if not SOURCE_LOGO.exists():
        raise FileNotFoundError(f"Application logo not found: {SOURCE_LOGO}")
    with Image.open(SOURCE_LOGO) as source:
        return source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def write_files():
    img = draw_icon(SZ)

    # SVG
    svg_path = ICONS_DIR / "app_icon.svg"
    svg_path.write_text(_svg_str("../../assets/logo.png"), encoding="utf-8")
    print(f"  SVG  -> {svg_path}")

    assets_svg = ASSETS_DIR / "app_icon.svg"
    assets_svg.write_text(_svg_str("logo.png"), encoding="utf-8")
    print(f"  SVG  -> {assets_svg}")

    # 主 PNG
    img.save(ICONS_DIR / "icon.png", "PNG")
    print(f"  PNG  -> icon.png ({SZ}x{SZ})")

    img.save(ASSETS_DIR / "app_icon.png", "PNG")
    print(f"  PNG  -> assets/app_icon.png")

    # 各尺寸
    sizes = {
        "128x128.png": 128, "128x128@2x.png": 256, "32x32.png": 32,
        "Square30x30Logo.png": 30, "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71, "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107, "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150, "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310, "StoreLogo.png": 50,
    }
    for name, px in sizes.items():
        img.resize((px, px), Image.LANCZOS).save(ICONS_DIR / name, "PNG")
        print(f"  PNG  -> {name} ({px}x{px})")

    # icns
    iconset_dir = ICONS_DIR / "app.iconset"
    iconset_dir.mkdir(exist_ok=True)
    icns_sizes = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for name, px in icns_sizes.items():
        img.resize((px, px), Image.LANCZOS).save(iconset_dir / name, "PNG")
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(ICONS_DIR / "icon.icns")],
        capture_output=True, check=True,
    )
    print(f"  ICNS -> icon.icns")
    shutil.copy2(ICONS_DIR / "icon.icns", ASSETS_DIR / "app_icon.icns")
    print(f"  ICNS -> assets/app_icon.icns")
    shutil.rmtree(iconset_dir)

    # ico
    ico_sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    ico_imgs = [img.resize(s, Image.LANCZOS) for s in ico_sizes]
    ico_imgs[0].save(ICONS_DIR / "icon.ico", format="ICO",
                     sizes=ico_sizes, append_images=ico_imgs[1:])
    print(f"  ICO  -> icon.ico")


def _svg_str(logo_href: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <image href="{logo_href}" width="512" height="512" preserveAspectRatio="xMidYMid slice"/>
</svg>'''


if __name__ == "__main__":
    print("Generating MiningProcessor icons...")
    write_files()
    print("Done.")
