# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目概述

这是一个**矿山数据处理** Python 项目，解析来自矿山运营的各类 Excel 报表，包括：

- 柴油/燃油消耗数据
- 生产数据（白班/夜班）
- 电力消耗
- 工时/矿卡作业数据

## 现有命令

所有脚本均基于 CLI，接受输入文件路径作为主参数：

```bash
# 处理燃油/柴油数据
python excel_fuel.py <输入文件> [--year 年份]

# 处理生产数据
python excel_production.py <输入文件夹路径> [--version 版本]

# 处理电力消耗
python excel_electrical.py <输入文件> [--year 年份]

# 处理工时/矿卡数据（支持文件或文件夹）
python excel_worktime.py <输入文件> [--year 年份] [--month 月份]
```

输出文件写入输入文件所在目录。

---

## 当前架构

项目包含 5 个独立的 Excel 处理脚本和一个模块化的 Flet 图形界面：

| 脚本 | 用途 | 输入格式 |
|------|------|---------|
| `excel_fuel.py` | 设备柴油消耗 | 包含"设备柴油消耗"的 Sheet |
| `excel_electrical.py` | 电力消耗 | 包含"Electrical"的 Sheet |
| `excel_worktime.py` | 矿卡/挖机作业 | 白班/夜班 Excel 文件 |
| `excel_production.py` | 生产效率表 | Sheet 名称为数字（1-31） |
| `excel_production_enhanced.py` | 增强版生产处理（多线程） | 白班/夜班文件夹 |
| `gui/` | Flet 图形界面 | 模块化结构 |

所有脚本使用 **pandas** 解析 Excel，输出结构化数据，列包含：日期、班次（Day/Night）、设备名称及各类指标（工时、燃油、产量等）。

---

## 图形化界面（模块化结构）

`gui/` 包采用三层结构：

```
gui/
  __init__.py   # 导出 main 入口
  main.py       # 页面组装、FilePicker（async 模式）
  components.py # UI 组件工厂函数（台账/配置/模块/日志）
  logic.py      # 业务逻辑（线程任务、按钮绑定、配置初始化）
```

**FilePicker 模式**：采用 Flet 官方推荐的 async 模式，每次点击时 `await ft.FilePicker().pick_files()`，无需 `page.overlay`。

支持功能：
- 设备台账导入/导出模板
- 设备装载量配置（GUI 可视化编辑）
- 4 个数据处理模块：燃油、生产（enhanced）、电力、工时
- 处理日志实时显示
- 页面可滚动，DataTable 不溢出

运行：`python gui/main.py` 或 `python -m gui`

---

## 配置管理

`config_loader.py` + `config.json` 管理设备型号与装载量映射：

```json
{
  "device_load_map": {
    "NTE240": 85,
    "TR100": 35,
    "EH4000": 85
  }
}
```

GUI 中可直接编辑配置，无需手动修改 JSON 文件。

---

## 设备台账与模糊匹配

设备台账（`equipment_ledger.py`）和模糊匹配**目前未启用**，仅在**多表合并**时使用。

待实现的多表合并场景中，设备名称格式不统一（如带编号、带空格），需要：
- 基于 rapidfuzz 的相似度匹配
- 支持前缀匹配、部分匹配
- 匹配结果可追溯（原始名称 → 标准名称）

---

## 待实现：多表联动

通过日期 + 设备名称（模糊匹配后）关联各表数据，生成综合统计报表。

---

## Python 版本

需要 Python 3.12+（见 `.python-version`）

---

## 实现文件清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `gui/main.py` | Flet GUI 主窗口 | 已完成 |
| `gui/components.py` | UI 组件工厂 | 已完成 |
| `gui/logic.py` | 业务逻辑 | 已完成 |
| `gui/__init__.py` | 包入口 | 已完成 |
| `config_loader.py` | 配置加载 | 已完成 |
| `equipment_ledger.py` | 设备台账模块 | 已完成（待启用） |
| `config.json` | 配置文件 | 已完成 |
| `pyproject.toml` | 依赖管理 | 已完成 |
| `excel_fuel.py` | 燃油处理 | 已完成 |
| `excel_electrical.py` | 电力处理 | 已完成 |
| `excel_worktime.py` | 工时/矿卡处理 | 已完成 |
| `excel_production_enhanced.py` | 增强版生产处理 | 已完成 |
| 模糊匹配 | 多表合并时启用 | 待实现 |