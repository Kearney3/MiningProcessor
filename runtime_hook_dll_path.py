# Runtime hook: 确保 PyInstaller 解压目录在 DLL 搜索路径中
# 解决 Windows 上 LoadLibrary 失败的问题
import os
import sys

if hasattr(sys, '_MEIPASS'):
    # 将 PyInstaller 解压目录加入 DLL 搜索路径
    os.add_dll_directory(sys._MEIPASS)
