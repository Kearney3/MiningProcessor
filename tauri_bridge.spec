# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 将 tauri_bridge.py + func/* + 依赖打包为单文件可执行程序。

用法:
  pyinstaller tauri_bridge.spec
  输出: dist/tauri-bridge (macOS) 或 dist/tauri-bridge.exe (Windows)
"""

import os
import sys
import glob

block_cipher = None

# 收集 func/ 目录下所有 Python 模块
func_datas = []
func_dir = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'func')
if os.path.isdir(func_dir):
    for f in os.listdir(func_dir):
        if f.endswith('.py') and f != '__pycache__':
            func_datas.append((os.path.join(func_dir, f), 'func'))

# config.json
config_json = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'config.json')
if os.path.isfile(config_json):
    func_datas.append((config_json, '.'))

# data/ 目录（台账缓存等）
data_dir = os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'data')
if os.path.isdir(data_dir):
    func_datas.append((data_dir, 'data'))

# Windows: 显式收集 Python DLL（含 VC++ 运行时依赖）
python_dlls = []
if os.name == 'nt':
    for dll in glob.glob(os.path.join(sys.prefix, '*.dll')):
        python_dlls.append((dll, '.'))

a = Analysis(
    ['tauri_bridge.py'],
    pathex=[],
    binaries=python_dlls,
    datas=func_datas,
    hiddenimports=[
        'pandas',
        'numpy',
        'openpyxl',
        'rapidfuzz',
        'func.excel_fuel',
        'func.excel_electrical',
        'func.excel_production_enhanced',
        'func.excel_worktime',
        'func.excel_worktime_multifile',
        'func.excel_merger',
        'func.excel_batch',
        'func.excel_utils',
        'func.equipment_ledger',
        'func.oil_ledger',
        'func.config_loader',
        'func.sync_to_minebase',
        'func.orchestration',
        'func.excel_formatter',
        'func.string_utils',
        'func.logger',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'PIL',
        'pytest',
        'IPython',
        'notebook',
        'psycopg2',
        'psycopg2-binary',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tauri-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,             # 去掉调试符号，减小体积
    upx=True,               # 压缩（需安装 upx）
    console=True,           # 需要 stdin/stdout/stderr 通信
)

# macOS .app bundle 图标（sidecar 是 console 应用，图标由 Tauri 管理）
_spec_dir = os.path.dirname(os.path.abspath(SPEC))
app_icon = os.path.join(_spec_dir, 'assets', 'app_icon.icns')
if not os.path.isfile(app_icon):
    app_icon = os.path.join(_spec_dir, 'src-tauri', 'icons', 'icon.icns')

if os.name == 'posix':  # macOS / Linux
    app = BUNDLE(
        exe,
        name='MiningProcessor.app',
        icon=app_icon if os.path.isfile(app_icon) else None,
        bundle_identifier='com.kearney.mining-processor',
    )
