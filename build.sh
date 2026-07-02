#!/bin/bash
# ═══════════════════════════════════════════════════════════
# build.sh — 构建 Tauri + PyInstaller 打包
#
# 流程：
#   1. PyInstaller 打包 Python → build-sidecar/tauri-bridge
#   2. pnpm tauri build（前端 + Rust + 自动嵌入 sidecar via externalBin）
#   3. 打包 DMG
#
# 注意：PyInstaller 输出目录用 build-sidecar/ 而非 dist/，
#       因为 Vite 的 pnpm build 会清空 dist/ 目录。
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SIDECAR_DIR="build-sidecar"
SIDECAR_BIN="$SIDECAR_DIR/tauri-bridge"

echo "═══ MiningProcessor Tauri Build ═══"

# ─── 1. PyInstaller ───
echo "[1/3] Building Python sidecar with PyInstaller..."
uv run pyinstaller tauri_bridge.spec \
    --distpath "$SIDECAR_DIR" \
    --clean --noconfirm 2>&1 | tail -5

if [ ! -f "$SIDECAR_BIN" ]; then
    echo "ERROR: PyInstaller output not found at $SIDECAR_BIN"
    exit 1
fi

# externalBin 要求带目标三元组后缀（构建时自动去掉）
HOST_ARCH=$(uname -m)
if [ "$HOST_ARCH" = "arm64" ]; then
    TARGET_TRIPLE="aarch64-apple-darwin"
else
    TARGET_TRIPLE="x86_64-apple-darwin"
fi
cp "$SIDECAR_BIN" "$SIDECAR_DIR/tauri-bridge-$TARGET_TRIPLE"
chmod +x "$SIDECAR_DIR/tauri-bridge-$TARGET_TRIPLE"
echo "  → $SIDECAR_BIN ($(du -h "$SIDECAR_BIN" | cut -f1))"

# ─── 2. Tauri build（.app，sidecar 由 externalBin 自动嵌入）───
echo "[2/3] Building Tauri application (.app)..."
source "$HOME/.cargo/env"
pnpm tauri build --bundles app

# ─── 3. 打包 DMG ───
echo "[3/3] Packaging DMG with hdiutil..."

BUNDLE_DIR="src-tauri/target/release/bundle/macos"
APP_DIR=$(find "$BUNDLE_DIR" -name "*.app" -maxdepth 1 | head -1)

if [ -z "$APP_DIR" ]; then
    echo "ERROR: .app bundle not found in $BUNDLE_DIR"
    exit 1
fi

DMG_DIR="src-tauri/target/release/bundle/dmg"
mkdir -p "$DMG_DIR"

# 从配置读取版本号和产品名
VERSION=$(grep -o '"version": *"[^"]*"' src-tauri/tauri.conf.json | head -1 | cut -d'"' -f4)
APP_NAME=$(basename "$APP_DIR")
DMG_NAME="${APP_NAME%.app}_${VERSION}_aarch64.dmg"
DMG_PATH="$DMG_DIR/$DMG_NAME"

# 创建临时挂载目录
STAGING_DIR=$(mktemp -d)
cp -R "$APP_DIR" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

rm -rf "$STAGING_DIR"

# 验证
echo ""
echo "═══ Build Complete ═══"
echo "App: $APP_DIR"
echo "DMG: $DMG_PATH"
