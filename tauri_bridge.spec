# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 将 tauri_bridge.py + func/* + 依赖打包为可执行程序。

用法:
  pyinstaller tauri_bridge.spec
  输出: dist/tauri-bridge/ 目录（onedir 模式，避免 Windows Defender 误杀）

注意: 使用 onedir 而非 onefile，因为 onefile 解压到 %TEMP%\_MEI* 会被
      Windows Defender 立即删除，导致 LoadLibrary 失败。
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
    dll_src = sys.base_prefix if hasattr(sys, 'base_prefix') else sys.prefix
    for dll in glob.glob(os.path.join(dll_src, '*.dll')):
        python_dlls.append((dll, '.'))
    dlls_subdir = os.path.join(dll_src, 'DLLs')
    if os.path.isdir(dlls_subdir):
        for dll in glob.glob(os.path.join(dlls_subdir, '*.dll')):
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
    runtime_hooks=['runtime_hook_dll_path.py'] if os.name == 'nt' else [],
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

# onedir 模式：exe 不内嵌二进制，文件放在同目录下
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='tauri-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    console=True,
)

# 收集所有依赖到目录
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='tauri-bridge',
)

# macOS .app bundle
_spec_dir = os.path.dirname(os.path.abspath(SPEC))
app_icon = os.path.join(_spec_dir, 'assets', 'app_icon.icns')
if not os.path.isfile(app_icon):
    app_icon = os.path.join(_spec_dir, 'src-tauri', 'icons', 'icon.icns')

if os.name == 'posix':
    app = BUNDLE(
        coll,
        name='MiningProcessor.app',
        icon=app_icon if os.path.isfile(app_icon) else None,
        bundle_identifier='com.kearney.mining-processor',
    )
