# MiningProcessor

矿山运营 Excel 报表批量处理工具，支持命令行和桌面 GUI 两种使用方式。

自动解析矿山各类生产、油耗、电耗、工时报表，提取结构化数据并输出标准化 Excel 文件。

## 功能概览

| 模块 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `excel_fuel.py` | 设备柴油消耗统计 | 设备柴油消耗表 | `Fuel.xlsx` |
| `excel_electrical.py` | 设备电耗统计 | 含 Electrical 的 sheet | 电耗汇总表 |
| `excel_worktime.py` | 工作效率统计 | 工时报表文件/文件夹 | 按年月命名的效率表 |
| `excel_production.py` | 白班/夜班生产报表解析 | 生产报表文件夹 | 生产数据汇总 |
| `excel_production_enhanced.py` | 增强版生产报表解析（GUI 默认） | 生产报表文件/文件夹 | 生产数据汇总 |
| `excel_merger.py` | 按关键字批量合并同结构 Excel | 文件夹 + 关键字 | 合并后的 Excel |

## 项目结构

```
MiningProcessor/
├── main.py                 # GUI 入口（uv run main.py）
├── gui/                    # Flet 桌面 GUI 编排层
│   ├── main.py             # 页面组装、全局日志初始化
│   ├── components/         # UI 控件创建
│   ├── logic.py            # 按钮事件 → 后台线程调度
│   └── theme.py            # 主题配置
├── func/                   # 核心处理引擎
│   ├── config_loader.py    # 配置读写与运行时管理
│   ├── equipment_ledger.py # 设备台账与模糊匹配
│   ├── logger.py           # 统一日志（CLI/GUI 共享）
│   └── excel_*.py          # 各报表处理器
├── config.json             # 持久化配置（设备装载量映射等）
├── tests/                  # pytest 测试（主要覆盖 GUI 组件）
├── Notebook/               # Jupyter 探索性分析笔记本
├── assets/fonts/           # GUI 字体资源
└── docs/                   # 文档目录
```

## 安装与环境

**Python 版本**：3.14（见 `.python-version`）

```bash
# 使用 uv 安装依赖
uv sync
```

核心依赖：`pandas` + `openpyxl`（Excel 处理）、`flet`（GUI）、`rapidfuzz`（设备名模糊匹配）

## 使用方式

### 启动 GUI

```bash
python gui/main.py
python -m gui
python -m flet gui/main.py
uv run main.py
```

GUI 提供完整的处理流程入口，包括：
- 各类报表处理触发
- 配置编辑（设备装载量映射）
- 实时日志展示
- 设备台账管理

### 命令行运行

```bash
# 油耗处理
uv run python func/excel_fuel.py <输入文件> --year 2025

# 电耗处理
uv run python func/excel_electrical.py <输入文件> --year 2025

# 工时统计
uv run python func/excel_worktime.py <输入文件或文件夹> --year 2025 --month 1

# 生产报表
uv run python func/excel_production.py <输入文件夹> --version <版本>
uv run python func/excel_production_enhanced.py <输入文件或文件夹>

# 批量合并
uv run python func/excel_merger.py <输入文件夹> <关键字> [--strip-time] [--sort '<json>']
```

处理结果默认写入输入文件所在目录。

## 配置说明

`config.json` 包含：

- **`device_load_map`**：设备型号 → 装载量（吨）映射，用于生产数据计算
- **`default_year` / `default_month`**：默认年月参数
- **`shift_mapping`**：班次名称映射（中/蒙文 → 英文）
- **`output_naming`**：输出文件命名规则

GUI 中"应用当前配置"仅更新运行时内存，"保存配置"才会写回文件。

## 运行测试

```bash
uv run pytest
uv run pytest tests/test_gui_components.py
uv run pytest tests/test_gui_components.py -k config
```

测试主要覆盖 `gui/components.py` 和 `gui/main.py` 的行为（按钮事件、配置落盘、日志线程分发）。

## 架构要点

**两层架构**：`func/` 是业务处理引擎，`gui/` 是薄编排层，不包含 Excel 解析逻辑。

**独立处理器**：各 `excel_*.py` 模块相互独立，不共享统一领域模型，各自解析特定报表结构。

**统一日志**：`func/logger.py` 提供 `logging` + `get_logger()`，CLI 直接输出控制台，GUI 通过 `QueueHandler` 推送到页面。新增处理逻辑请使用 `logging` 而非 `print()`。

**设备台账**：`equipment_ledger.py` 支持标准名称、别名、前缀、rapidfuzz 相似度匹配，可用于跨报表设备名称归一化。

## 许可证

私有项目。
