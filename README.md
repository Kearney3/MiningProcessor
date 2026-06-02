# MiningProcessor

矿山运营 Excel 报表批量处理工具。支持 CLI 命令行和 Flet 桌面 GUI 两种使用方式，自动解析矿山各类生产、油耗、电耗、工时报表，提取结构化数据并输出标准化 Excel。

> **Python** ≥ 3.12（开发环境 3.14） · **依赖管理** [uv](https://docs.astral.sh/uv/) · **GUI 框架** [Flet](https://flet.dev/)

---

## 功能模块

| 入口 | CLI 命令 | 功能 | 输入 | 输出 |
|------|----------|------|------|------|
| `excel_fuel.py` | `fuel` | 设备柴油消耗统计 | 设备柴油消耗表 | `Fuel.xlsx` |
| `excel_electrical.py` | `electrical` | 设备电耗统计 | 含 `Electrical` 的 sheet | 电耗汇总表 |
| `excel_worktime.py` | `worktime` | 工作效率统计 | 工时报表文件/文件夹 | 按年月命名的效率表 |
| `excel_worktime_multifile.py` | `worktime-batch` | 工时批量处理 | 工时报表文件夹 | 多文件汇总 |
| `excel_production.py` | `production-old` | 白班/夜班生产报表解析 | 生产报表文件夹 | 生产数据汇总 |
| `excel_production_enhanced.py` | `production` | 增强版生产报表解析（GUI 默认） | 生产报表文件/文件夹 | 生产数据汇总 |
| `excel_merger.py` | `merge` | 按关键字批量合并同结构 Excel | 文件夹 + 关键字 | 合并后的 Excel |
| `excel_batch.py` | — | 批量多报表综合处理 | 文件夹 | 综合统计表 |

---

## 快速开始

### 环境准备

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆仓库
git clone <repo-url> && cd MiningProcessor

# 安装依赖（含 dev 工具）
uv sync
```

### 启动 GUI

```bash
# 推荐方式
uv run main.py

# 其他等效方式
uv run python gui/main.py
uv run python -m gui
```

GUI 提供完整的处理流程入口：

- 各类报表一键处理
- 配置编辑（设备装载量映射、班次名称等）
- 用户配置菜单（数据库连接、工作效率表头映射）
- 实时日志展示
- 设备台账管理（支持设备名称模糊匹配、编号匹配）

### 命令行使用

所有 CLI 命令均通过 `uv run` 执行，处理结果默认写入输入文件所在目录。

```bash
# 油耗处理
uv run fuel <输入文件> --year 2025

# 电耗处理
uv run electrical <输入文件> --year 2025

# 工时统计
uv run worktime <输入文件或文件夹> --year 2025 --month 1

# 生产报表（增强版）
uv run production <输入文件或文件夹>

# 批量合并
uv run merge <输入文件夹> <关键字> [--strip-time] [--sort '<json>']
```

也可使用传统 `python func/excel_*.py` 方式运行。

---

## 项目结构

```
MiningProcessor/
├── main.py                     # GUI 入口
├── gui/                        # Flet 桌面 GUI 编排层
│   ├── main.py                 # 页面组装、全局日志初始化
│   ├── components/             # UI 控件创建（模块化拆分）
│   │   ├── modules.py          # 报表处理模块面板
│   │   ├── config.py           # 配置编辑面板
│   │   ├── batch.py            # 批量处理面板
│   │   ├── ledger.py           # 设备台账面板
│   │   ├── ledger_match.py     # 台账匹配面板
│   │   ├── oil_ledger.py       # 油品台账面板
│   │   ├── user_config.py      # 用户配置面板
│   │   ├── log_view.py         # 日志视图
│   │   ├── common.py           # 公共组件
│   │   └── types.py            # 类型定义
│   ├── logic.py                # 按钮事件 → 后台线程调度
│   └── theme.py                # 主题配置
├── func/                       # 核心处理引擎
│   ├── config_loader.py        # 配置读写与运行时管理
│   ├── equipment_ledger.py     # 设备台账与模糊匹配
│   ├── oil_ledger.py           # 油品台账管理
│   ├── logger.py               # 统一日志（CLI/GUI 共享）
│   └── excel_*.py              # 各报表处理器
├── config.json                 # 持久化配置
├── tests/                      # pytest 测试（233 个用例）
├── assets/fonts/               # GUI 字体资源（MiSans 可变字体）
├── Notebook/                   # Jupyter 探索性分析笔记本
├── docs/                       # 文档目录
└── .github/workflows/          # CI：Flet 桌面应用构建
```

---

## 配置说明

项目采用双配置文件机制：

- **`config.json`**：系统默认配置，提交到 Git，包含设备映射、班次名称等公共设置。
- **`config.user.json`**：用户覆盖配置（已 gitignore），包含数据库凭据、工作效率表头映射等敏感/个性化设置。`load_config()` 运行时自动合并两者（user 覆盖 default）。

`config.json` 主要配置项：

| 配置项 | 说明 |
|--------|------|
| `device_load_map` | 设备型号 → 装载量（吨）映射，用于生产数据计算 |
| `device_load_map_old` | 旧版装载量映射（历史兼容） |
| `default_year` / `default_month` | 默认年月参数 |
| `shift_mapping` | 班次名称映射（中/蒙文 → 英文） |
| `output_naming` | 输出文件命名规则（是否含日期、班次） |
| `worktime_header_apply` | 是否应用自定义表头映射 |
| `user_config_default` | 用户配置默认值（`database`、`file_keywords`） |

`config.user.json` 主要配置项：

| 配置项 | 说明 |
|--------|------|
| `user_config.database` | 数据库连接参数（`db_type/host/port/name/user/password`） |
| `user_config.worktime_header_mapping` | 工作效率表自定义表头映射（支持位置模式和模糊匹配） |
| `user_config.file_keywords` | 各报表文件识别关键字 |

> **注意**：GUI 中"应用当前配置"仅更新运行时内存（`apply_device_load_map()`），"保存配置"才会写回文件（`update_device_load_map()`）。

---

## 架构设计

### 两层架构

- **`func/`**：业务处理引擎，负责 Excel 解析、数据提取、日志、配置管理。
- **`gui/`**：薄编排层，负责 UI 控件创建、用户输入收集、后台任务调度，不包含 Excel 解析逻辑。

### 独立处理器

各 `excel_*.py` 模块相互独立，各自解析特定报表结构，不共享统一领域模型。新增处理模块时：

1. 在 `func/` 下编写处理函数，使用 `logging` / `get_logger()` 打日志；
2. 在 `gui/components/` 增加输入控件；
3. 在 `gui/logic.py` 的 `_execute_task()` 和按钮回调中接入处理函数。

### 统一日志

`func/logger.py` 提供 `logging` + `get_logger()`，CLI 直接输出控制台，GUI 通过 `QueueHandler` 推送到页面日志列表。新增处理逻辑请使用 `logging` 而非 `print()`。

### 设备台账

`func/equipment_ledger.py` 支持标准名称、别名、前缀、`rapidfuzz` 相似度匹配，可用于跨报表设备名称归一化。生产数据处理时，若同时存在"矿卡名称"和"挖机名称"列，匹配结果会自动添加后缀区分。

---

## 测试

```bash
# 运行全部测试（233 个用例）
uv run pytest

# 运行指定测试文件
uv run pytest tests/test_gui_components.py
uv run pytest tests/test_config_loader.py
uv run pytest tests/test_excel_merger.py

# 按关键字过滤
uv run pytest tests/test_gui_components.py -k config

# 查看详细输出
uv run pytest -v
```

测试覆盖范围：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_gui_components.py` | GUI 组件行为、布局、按钮交互 |
| `test_config_loader.py` | 配置读写落盘、默认值合并、运行时配置 |
| `test_logic_helpers.py` | GUI 逻辑辅助函数 |
| `test_excel_merger.py` | Excel 合并与排序 |
| `test_table_merge.py` | 表内合并聚合 |
| `test_logger.py` / `test_log_consumer.py` | 日志格式化、队列分发 |
| `test_ledger_mapping.py` / `test_ledger_match_improvements.py` | 设备台账匹配与后缀 |
| `test_oil_ledger.py` | 油品台账管理 |
| `test_user_config_section.py` | 用户配置面板 |
| `test_production_config_flow.py` | 生产配置流程 |
| `test_tab_switching.py` | Tab 切换行为 |
| `test_drag_resize.py` | 拖拽调整 |

---

## 构建桌面应用

项目配置了 GitHub Actions 自动构建 Flet 桌面应用（macOS / Windows），详见 `.github/workflows/build-flet-client.yml`。

本地构建：

```bash
uv run flet build macos   # macOS
uv run flet build windows # Windows
```

---

## 许可证

MIT License。
