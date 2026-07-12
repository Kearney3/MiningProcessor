#!/bin/bash
# ═══════════════════════════════════════════════════════════
# build.sh — 构建 Tauri + PyInstaller 打包
#
# 流程：
#   1. PyInstaller 打包 Python → build-sidecar/tauri-bridge/ 目录
#   2. pnpm tauri build
#   3. 将 sidecar 目录嵌入 .app bundle
#   4. 打包 DMG
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SIDECAR_DIR="build-sidecar"

echo "═══ MiningProcessor Tauri Build ═══"

# ─── 1. PyInstaller（onedir 模式）───
echo "[1/4] Building Python sidecar with PyInstaller..."
uv run pyinstaller tauri_bridge.spec \
    --distpath "$SIDECAR_DIR" \
    --clean --noconfirm 2>&1 | tail -5

SIDECAR_BIN="$SIDECAR_DIR/tauri-bridge/tauri-bridge"
if [ ! -f "$SIDECAR_BIN" ]; then
    echo "ERROR: PyInstaller output not found at $SIDECAR_BIN"
    exit 1
fi
echo "  → $SIDECAR_BIN ($(du -sh "$SIDECAR_DIR/tauri-bridge" | cut -f1))"

# ─── 2. Tauri build ───
echo "[2/4] Building Tauri application (.app)..."
source "$HOME/.cargo/env"
pnpm tauri build --bundles app

# ─── 3. 嵌入 sidecar 到 .app bundle ───
echo "[3/4] Embedding sidecar into app bundle..."
BUNDLE_DIR="src-tauri/target/release/bundle/macos"

APP_DIR=$(find "$BUNDLE_DIR" -name "*.app" -maxdepth 1 | head -1)
if [ -z "$APP_DIR" ]; then
    echo "ERROR: .app bundle not found in $BUNDLE_DIR"
    exit 1
fi

cp -R "$SIDECAR_DIR/tauri-bridge" "$APP_DIR/Contents/Resources/tauri-bridge"
chmod +x "$APP_DIR/Contents/Resources/tauri-bridge/tauri-bridge"
codesign --force --sign - "$APP_DIR/Contents/Resources/tauri-bridge/tauri-bridge" 2>/dev/null || true
codesign --force --sign - "$APP_DIR" 2>/dev/null || true
echo "  → Embedded: $APP_DIR/Contents/Resources/tauri-bridge/"

# ─── 4. 打包 DMG ───
echo "[4/4] Packaging DMG with hdiutil..."
DMG_DIR="src-tauri/target/release/bundle/dmg"
mkdir -p "$DMG_DIR"

VERSION=$(grep -o '"version": *"[^"]*"' src-tauri/tauri.conf.json | head -1 | cut -d'"' -f4)
APP_NAME=$(basename "$APP_DIR")
DMG_NAME="${APP_NAME%.app}_${VERSION}_aarch64.dmg"
DMG_PATH="$DMG_DIR/$DMG_NAME"

STAGING_DIR=$(mktemp -d)
cp -R "$APP_DIR" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING_DIR" -ov -format UDZO "$DMG_PATH"
rm -rf "$STAGING_DIR"

echo ""
echo "═══ Bundle Contents ═══"
ls -lh "$APP_DIR/Contents/Resources/tauri-bridge/"

echo ""
echo "═══ Build Complete ═══"
echo "App: $APP_DIR"
echo "DMG: $DMG_PATH"
