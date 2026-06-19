"""
MiningProcessor 应用图标生成器
纯矿山设计 - Pillow 绘制
"""
from pathlib import Path
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFilter

ICONS_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ICONS_DIR.parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

SZ = 512
CORNER = 96

# 色彩 (R, G, B)
C_BG      = (12, 18, 35)
C_BG2     = (22, 32, 58)
C_MTN_DK  = (14, 110, 128)   # 暗面
C_MTN_MD  = (22, 148, 168)   # 中间
C_MTN_LT  = (36, 188, 210)   # 亮面
C_MTN_HL  = (55, 210, 230)   # 高光
C_VEIN    = (245, 170, 40)
C_VEIN2   = (220, 148, 28)


def draw_icon(size: int) -> Image.Image:
    s = size / SZ
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=int(CORNER*s), fill=C_BG)
    # 背景微渐变（底部略亮）
    for i in range(int(180*s)):
        y = int(330*s) + i
        if y >= size: break
        t = i / (180*s)
        r = int(C_BG[0] + (C_BG2[0]-C_BG[0])*t)
        g = int(C_BG[1] + (C_BG2[1]-C_BG[1])*t)
        b = int(C_BG[2] + (C_BG2[2]-C_BG[2])*t)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    def pt(x, y):
        return (int(x*s), int(y*s))

    def poly(pts, fill):
        draw.polygon([pt(x,y) for x,y in pts], fill=fill)

    def triangle_halfs(x1,y1, x2,y2, x3,y3, left_c, right_c):
        """Draw a triangle split at the peak into left/right faces"""
        poly([(x1,y1),(x2,y2),(x2,y3)], left_c)
        poly([(x2,y2),(x3,y3),(x2,y3)], right_c)

    # --- 背景山层 ---
    triangle_halfs(10,440, 100,268, 190,440,
                   (16,88,102), (20,105,118))
    triangle_halfs(310,440, 410,252, 502,440,
                   (16,88,102), (20,105,118))

    # --- 中景山层 ---
    triangle_halfs(22,440, 128,228, 234,440,
                   C_MTN_DK, C_MTN_MD)
    triangle_halfs(278,440, 384,218, 490,440,
                   C_MTN_DK, (26,160,180))

    # --- 主峰（中央） ---
    triangle_halfs(138,440, 256,168, 374,440,
                   C_MTN_MD, C_MTN_LT)

    # --- 前景小丘 ---
    triangle_halfs(-8,440, 72,358, 152,440,
                   (12,98,114), (18,120,138))
    triangle_halfs(360,440, 440,348, 520,440,
                   (12,98,114), (18,120,138))

    # --- 金色矿脉 ---
    veins = [
        ([(100,290),(88,340),(115,312)], C_VEIN, 0.85),
        ([(82,355),(75,395),(100,372)],  C_VEIN, 0.65),
        ([(232,200),(218,260),(250,232)],C_VEIN, 0.9),
        ([(210,280),(200,330),(228,305)],C_VEIN, 0.75),
        ([(265,240),(255,290),(278,265)],C_VEIN, 0.6),
        ([(365,250),(350,305),(380,278)],C_VEIN, 0.85),
        ([(342,320),(332,368),(358,342)],C_VEIN, 0.65),
        ([(48,380),(42,410),(60,395)],   C_VEIN2,0.5),
        ([(430,365),(422,400),(445,382)],C_VEIN2,0.5),
    ]
    for pts, color, opacity in veins:
        overlay = Image.new("RGBA", (size, size), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        od.polygon([pt(x,y) for x,y in pts], fill=(*color, int(255*opacity)))
        img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- 主峰高光边缘（rim light）---
    # 左侧边缘
    draw.line([pt(138,440), pt(256,168)], fill=(*C_MTN_HL, 120), width=max(1,int(3*s)))
    # 右侧边缘
    draw.line([pt(374,440), pt(256,168)], fill=(*C_MTN_HL, 80),  width=max(1,int(2*s)))

    # --- 主峰顶部微光 ---
    glow = Image.new("RGBA", (size, size), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    cx, cy = pt(256, 172)
    rad = int(32*s)
    for i in range(rad, 0, -1):
        a = int(35 * (1 - i/rad))
        gd.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(180, 230, 240, a))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # --- 底部渐变遮罩 ---
    for i in range(int(70*s)):
        y = int(380*s) + i
        if y >= size: break
        a = int(180 * (i/(70*s)))
        draw.line([(0, y), (size, y)], fill=(*C_BG, a))

    return img


def write_files():
    img = draw_icon(SZ)

    # SVG
    svg_path = ICONS_DIR / "app_icon.svg"
    svg_path.write_text(_svg_str(), encoding="utf-8")
    print(f"  SVG  -> {svg_path}")

    assets_svg = ASSETS_DIR / "app_icon.svg"
    assets_svg.write_text(_svg_str(), encoding="utf-8")
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


def _svg_str() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.5" y2="1">
      <stop offset="0%" stop-color="#0C1223"/>
      <stop offset="100%" stop-color="#162040"/>
    </linearGradient>
    <linearGradient id="v1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#F5AA28"/>
      <stop offset="100%" stop-color="#DC941C"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.33" r="0.12">
      <stop offset="0%" stop-color="#B4E6F0" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="#B4E6F0" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="512" height="512" rx="96" fill="url(#bg)"/>

  <!-- 背景山 -->
  <polygon points="10,440 100,268 190,440" fill="#105866"/>
  <polygon points="100,268 190,440 100,440" fill="#146976"/>
  <polygon points="310,440 410,252 502,440" fill="#105866"/>
  <polygon points="410,252 502,440 410,440" fill="#146976"/>

  <!-- 中景山 -->
  <polygon points="22,440 128,228 234,440" fill="#0E6E80"/>
  <polygon points="128,228 234,440 128,440" fill="#1694A8"/>
  <polygon points="278,440 384,218 490,440" fill="#0E6E80"/>
  <polygon points="384,218 490,440 384,440" fill="#1AA0B4"/>

  <!-- 主峰 -->
  <polygon points="138,440 256,168 374,440" fill="#1694A8"/>
  <polygon points="256,168 374,440 256,440" fill="#24BCD2"/>

  <!-- 前景小丘 -->
  <polygon points="-8,440 72,358 152,440" fill="#0C6272"/>
  <polygon points="72,358 152,440 72,440" fill="#12788A"/>
  <polygon points="360,440 440,348 520,440" fill="#0C6272"/>
  <polygon points="440,348 520,440 440,440" fill="#12788A"/>

  <!-- 矿脉 -->
  <path d="M100,290 L88,340 115,312Z" fill="url(#v1)" opacity="0.85"/>
  <path d="M82,355 L75,395 100,372Z" fill="url(#v1)" opacity="0.65"/>
  <path d="M232,200 L218,260 250,232Z" fill="url(#v1)" opacity="0.9"/>
  <path d="M210,280 L200,330 228,305Z" fill="url(#v1)" opacity="0.75"/>
  <path d="M265,240 L255,290 278,265Z" fill="url(#v1)" opacity="0.6"/>
  <path d="M365,250 L350,305 380,278Z" fill="url(#v1)" opacity="0.85"/>
  <path d="M342,320 L332,368 358,342Z" fill="url(#v1)" opacity="0.65"/>
  <path d="M48,380 L42,410 60,395Z" fill="url(#v1)" opacity="0.5"/>
  <path d="M430,365 L422,400 445,382Z" fill="url(#v1)" opacity="0.5"/>

  <!-- 主峰高光边缘 -->
  <line x1="138" y1="440" x2="256" y2="168" stroke="#37D2E6" stroke-opacity="0.45" stroke-width="3"/>
  <line x1="374" y1="440" x2="256" y2="168" stroke="#37D2E6" stroke-opacity="0.28" stroke-width="2"/>

  <!-- 峰顶微光 -->
  <circle cx="256" cy="172" r="32" fill="url(#glow)"/>

  <!-- 底部渐变 -->
  <defs>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0C1223" stop-opacity="0"/>
      <stop offset="100%" stop-color="#0C1223" stop-opacity="0.7"/>
    </linearGradient>
  </defs>
  <rect x="0" y="380" width="512" height="132" fill="url(#fade)"/>
</svg>'''


if __name__ == "__main__":
    print("Generating MiningProcessor icons...")
    write_files()
    print("Done.")
