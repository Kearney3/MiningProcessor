#!/bin/bash
# ═══════════════════════════════════════════════════════════
# build.sh — 构建 Tauri + PyInstaller 打包
#
# 流程：
#   1. uv 同步 Python 依赖
#   2. PyInstaller 打包 Python → dist/tauri-bridge
#   3. pnpm tauri build
#   4. 将 sidecar 嵌入 macOS .app bundle
# ═══════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══ MiningProcessor Tauri Build ═══"

# ─── 1. Python 依赖 ───
echo "[1/4] Syncing Python dependencies..."
uv sync --dev

# ─── 2. PyInstaller ───
echo "[2/4] Building Python sidecar with PyInstaller..."
uv run pyinstaller tauri_bridge.spec --clean --noconfirm 2>&1 | tail -5

SIDECAR_SRC="dist/tauri-bridge"
if [ ! -f "$SIDECAR_SRC" ]; then
    echo "ERROR: PyInstaller output not found at $SIDECAR_SRC"
    exit 1
fi
echo "  → $SIDECAR_SRC ($(du -h "$SIDECAR_SRC" | cut -f1))"

# ─── 3. Tauri build ───
echo "[3/4] Building Tauri application..."
source "$HOME/.cargo/env"
pnpm tauri build

# ─── 4. 嵌入 sidecar 到 .app bundle ───
echo "[4/4] Embedding sidecar into app bundle..."

BUNDLE_DIR="src-tauri/target/release/bundle"

# macOS
if [ -d "$BUNDLE_DIR/macos" ]; then
    APP_DIR=$(find "$BUNDLE_DIR/macos" -name "*.app" -maxdepth 1 | head -1)
    if [ -n "$APP_DIR" ]; then
        cp "$SIDECAR_SRC" "$APP_DIR/Contents/MacOS/tauri-bridge"
        chmod +x "$APP_DIR/Contents/MacOS/tauri-bridge"
        echo "  → Embedded in $APP_DIR/Contents/MacOS/tauri-bridge"

        # 重新签名（ad-hoc）
        codesign --force --sign - "$APP_DIR/Contents/MacOS/tauri-bridge" 2>/dev/null || true
        codesign --force --sign - "$APP_DIR" 2>/dev/null || true
        echo "  → Re-signed app bundle"
    fi
fi

# Linux
if [ -d "$BUNDLE_DIR/deb" ] || [ -d "$BUNDLE_DIR/appimage" ]; then
    echo "  → Linux bundle detected, sidecar should be placed manually"
fi

echo ""
echo "═══ Build complete ═══"
echo "macOS app: $BUNDLE_DIR/macos/"
echo "DMG:       $BUNDLE_DIR/dmg/"
