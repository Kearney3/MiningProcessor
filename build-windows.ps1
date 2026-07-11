# ═══════════════════════════════════════════════════════════
# build-windows.ps1 - Windows 构建脚本 (Tauri + PyInstaller)
#
# 流程：
#   1. PyInstaller 打包 Python → build-sidecar/tauri-bridge.exe
#   2. 重命名为 Tauri externalBin 期望的带架构后缀格式
#   3. pnpm tauri build（externalBin 自动嵌入 NSIS 安装包）
# ═══════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

$SIDECAR_DIR = "build-sidecar"
$SIDECAR_BIN = "$SIDECAR_DIR\tauri-bridge.exe"

Write-Host "═══ MiningProcessor Tauri Build (Windows) ═══" -ForegroundColor Cyan

# ─── 1. PyInstaller（使用 Python 3.12，高版本兼容性问题）───
Write-Host "[1/2] Building Python sidecar with PyInstaller..." -ForegroundColor Yellow
uv run --python 3.12 pyinstaller tauri_bridge.spec `
    --distpath $SIDECAR_DIR `
    --clean --noconfirm 2>&1 | Select-Object -Last 5

if (-not (Test-Path $SIDECAR_BIN)) {
    Write-Host "ERROR: PyInstaller output not found at $SIDECAR_BIN" -ForegroundColor Red
    exit 1
}
$size = (Get-Item $SIDECAR_BIN).Length / 1MB
Write-Host "  -> $SIDECAR_BIN ($([math]::Round($size, 1)) MB)" -ForegroundColor Green

# ─── 2. 重命名为 Tauri externalBin 期望的格式 ───
$SIDECAR_TARGET = "$SIDECAR_DIR\tauri-bridge-x86_64-pc-windows-msvc.exe"
Rename-Item $SIDECAR_BIN $SIDECAR_TARGET -Force
Write-Host "  -> Renamed to: $SIDECAR_TARGET" -ForegroundColor Green

# ─── 3. Tauri build（externalBin 自动嵌入 NSIS 安装包）───
Write-Host "[2/2] Building Tauri application (NSIS)..." -ForegroundColor Yellow
cargo tauri build --bundles nsis

$NSIS_DIR = "src-tauri\target\release\bundle\nsis"
Write-Host ""
Write-Host "═══ Build Complete ═══" -ForegroundColor Cyan
Get-ChildItem $NSIS_DIR | Format-Table Name, Length -AutoSize
