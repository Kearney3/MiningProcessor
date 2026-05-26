"""
func 包初始化
集中设置项目根目录到 sys.path，使所有 func/ 下模块可通过标准包导入。
保留此机制以支持 `python func/excel_fuel.py` 的直接运行方式。
"""
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
