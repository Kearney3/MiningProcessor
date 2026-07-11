# ═══════════════════════════════════════════════════════════
# build-windows.ps1 - Windows 构建脚本 (Tauri + PyInstaller)
#
# 流程：
#   1. PyInstaller 打包 Python → build-sidecar/tauri-bridge.exe
#   2. pnpm tauri build（前端 + Rust，生成 NSIS 安装包）
#   3. 将 tauri-bridge.exe 嵌入 NSIS 输出目录
# ═══════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

$SIDECAR_DIR = "build-sidecar"
$SIDECAR_BIN = "$SIDECAR_DIR\tauri-bridge.exe"

Write-Host "═══ MiningProcessor Tauri Build (Windows) ═══" -ForegroundColor Cyan

# ─── 1. PyInstaller ───
Write-Host "[1/3] Building Python sidecar with PyInstaller..." -ForegroundColor Yellow
uv run pyinstaller tauri_bridge.spec `
    --distpath $SIDECAR_DIR `
    --clean --noconfirm 2>&1 | Select-Object -Last 5

if (-not (Test-Path $SIDECAR_BIN)) {
    Write-Host "ERROR: PyInstaller output not found at $SIDECAR_BIN" -ForegroundColor Red
    exit 1
}
$size = (Get-Item $SIDECAR_BIN).Length / 1MB
Write-Host "  -> $SIDECAR_BIN ($([math]::Round($size, 1)) MB)" -ForegroundColor Green

# ─── 2. Tauri build（NSIS）───
Write-Host "[2/3] Building Tauri application (NSIS)..." -ForegroundColor Yellow
cargo tauri build --bundles nsis

# ─── 3. 嵌入 sidecar 到 NSIS 输出目录 ───
Write-Host "[3/3] Embedding sidecar into NSIS output..." -ForegroundColor Yellow

$NSIS_DIR = "src-tauri\target\release\bundle\nsis"

if (-not (Test-Path $NSIS_DIR)) {
    Write-Host "ERROR: NSIS output not found at $NSIS_DIR" -ForegroundColor Red
    exit 1
}

Copy-Item $SIDECAR_BIN "$NSIS_DIR\tauri-bridge.exe" -Force
Write-Host "  -> Embedded: $NSIS_DIR\tauri-bridge.exe" -ForegroundColor Green

Write-Host ""
Write-Host "═══ Build Complete ═══" -ForegroundColor Cyan
Get-ChildItem $NSIS_DIR | Format-Table Name, Length -AutoSize
