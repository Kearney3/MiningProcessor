# ⛏️ MiningProcessor

> 矿山运营 Excel 报表批量处理工具

<p>
  <img src="https://img.shields.io/badge/version-v1.2.0-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/Python-≥3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square" alt="license" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey?style=flat-square" alt="platform" />
  <img src="https://img.shields.io/badge/Tauri-v2-FFC131?style=flat-square&logo=tauri&logoColor=black" alt="tauri" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="react" />
  <img src="https://img.shields.io/badge/tests-887%20passed-brightgreen?style=flat-square" alt="tests" />
</p>

<p>
  <strong>CLI</strong> 命令行 + <strong>Tauri 桌面 GUI</strong> + <strong>Flet 桌面 GUI</strong> 三入口<br/>
  自动解析矿山生产、油耗、电耗、工时报表 → 结构化数据 → 标准化 Excel
</p>

---

## 📦 功能模块

| 入口 | CLI 命令 | 功能 | 输入 | 输出 |
|------|----------|------|------|------|
| `excel_fuel.py` | `fuel` | 设备柴油消耗统计 | 设备柴油消耗表 | `Fuel.xlsx` |
| `excel_electrical.py` | `electrical` | 设备电耗统计 | 含 `Electrical` 的 sheet | 电耗汇总表（可选班次列） |
| `excel_worktime.py` | `worktime` | 工作效率统计 | 工时报表文件或文件夹（自动识别） | 按年月命名的效率表 |
| `excel_worktime_multifile.py` | — | 多文件夹工时处理（由 `worktime` 自动调用） | 按日期分子文件夹的工时报表 | 多文件汇总 |
| `excel_production_enhanced.py` | `production` | 增强版生产报表解析（GUI 默认） | 生产报表文件/文件夹 | 生产数据汇总 |
| `excel_merger.py` | `merge` | 按关键字批量合并同结构 Excel | 文件夹 + 关键字 | 合并后的 Excel |
| `excel_batch.py` | — | 批量多报表综合处理 | 文件夹 | 综合统计表 |
| `anomaly/` | — | 异常值检测与处理 | 各类 DataFrame | 标记/过滤/替换 + 异常报告 |

---

## 🚀 快速开始

### 环境准备

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆仓库
git clone <repo-url> && cd MiningProcessor

# 安装 Python 依赖（含 dev 工具）
uv sync

# 安装前端依赖
pnpm install
```

### 启动开发环境

```bash
# 一键启动（Python sidecar + Vite 前端 + Tauri 窗口）
pnpm tauri dev

# 仅启动 Python sidecar
pnpm dev:bridge
```

**GUI 功能一览：**

- 各类报表一键处理（电力模块可选添加班次列）
- 跳过隐藏行 / 跳过隐藏列（独立开关，数据处理、批量处理、数据同步均支持；同步模块默认开启跳过隐藏行）
- 配置编辑（设备装载量映射、班次名称等）
- 用户配置菜单（数据库连接、工作效率表头映射）
- 实时日志展示
- 设备台账管理（支持设备名称模糊匹配、编号匹配）
- 异常值检测（阈值 / σ 异常 / 百分位，支持标记、过滤、替换默认值三种处理模式）

### 命令行使用

所有 CLI 命令均通过 `uv run` 执行，处理结果默认写入输入文件所在目录。

```bash
# 油耗处理
uv run fuel <输入文件> --year 2025

# 电耗处理
uv run electrical <输入文件> --year 2025
uv run electrical <输入文件> --year 2025 --add-shift  # 新增班次列 (Day/Night)

# 工时统计（支持单文件或文件夹，自动识别）
uv run worktime <输入文件或文件夹> --year 2025 --month 1

# 生产报表（增强版）
uv run production <输入文件或文件夹>

# 批量合并
uv run merge <输入文件夹> <关键字> [--strip-time] [--sort '<json>']

# 所有命令均支持跳过隐藏行/列
uv run fuel <输入文件> --year 2025 --skip-hidden-rows           # 仅跳过隐藏行
uv run fuel <输入文件> --year 2025 --skip-hidden-cols           # 仅跳过隐藏列
uv run fuel <输入文件> --year 2025 --skiphidden                 # 同时跳过（向后兼容）
```

也可使用传统 `python func/excel_*.py` 方式运行。

---

## 🏗️ 项目结构

```
MiningProcessor/
├── src/                        # React 前端 (Tauri GUI)
│   ├── main.tsx                # 前端入口
│   ├── App.tsx                 # 主应用（数据处理页）
│   ├── styles.css              # 全局样式（MiSans 字体）
│   ├── hooks/
│   │   ├── usePythonBridge.ts  # 与 Python sidecar 的通信桥接
│   │   └── useLastDirectory.ts # 记住上次目录
│   ├── lib/
│   │   ├── types.ts            # TypeScript 类型定义
│   │   ├── icons.tsx           # 图标库
│   │   └── ui-classes.ts       # UI class 名常量
│   ├── components/             # UI 组件
│   │   ├── Sidebar.tsx         # 左侧导航栏
│   │   ├── LogPanel.tsx        # 底部日志面板
│   │   ├── Toast.tsx           # 通知
│   │   ├── ConnectionStatusBadge.tsx
│   │   ├── DatePicker.tsx      # 日期选择
│   │   └── pages/              # 各功能页面（数据处理/批量/台账/同步等 9 个）
│   └── test/                   # Vitest 测试（6 个用例文件）
├── src-tauri/                  # Rust 壳进程
│   ├── src/main.rs             # Tauri 入口
│   ├── src/lib.rs              # 窗口配置与日志初始化
│   ├── src/python_bridge.rs    # Python sidecar 管理（spawn/poll/restart）
│   ├── capabilities/default.json
│   ├── icons/                  # 应用图标
│   └── Cargo.toml
├── func/                       # 核心处理引擎（Python）
│   ├── config_loader.py        # 配置读写与运行时管理
│   ├── secret_store.py         # Keychain 凭证存储（密码加密）
│   ├── equipment_ledger.py     # 设备台账与模糊匹配
│   ├── oil_ledger.py           # 油品台账管理
│   ├── ledger_base.py / ledger_match.py / ledger_postprocess.py
│   ├── logger.py               # 统一日志（CLI/GUI 共享）
│   ├── orchestration.py        # 多报表编排处理
│   ├── path_utils.py           # 路径安全校验
│   ├── string_utils.py         # 字符串清理工具
│   ├── excel_utils.py          # Excel 共享工具（日期标准化、班次分割、隐藏行列过滤）
│   ├── excel_formatter.py      # 输出格式化
│   ├── excel_fuel.py           # 油耗处理
│   ├── excel_electrical.py     # 电耗处理
│   ├── excel_worktime.py       # 工时处理
│   ├── excel_worktime_multifile.py  # 工时批量处理
│   ├── excel_production_enhanced.py # 生产报表（GUI 默认）
│   ├── excel_merger.py         # 多文件合并
│   ├── excel_batch.py          # 批量综合处理
│   ├── anomaly/                # 异常值检测与处理
│   │   ├── __init__.py         # detect_and_filter() 门面函数
│   │   ├── rules.py            # 规则定义（阈值/σ/百分位）+ AnomalyConfig
│   │   ├── detector.py         # 检测引擎
│   │   ├── filters.py          # 过滤器（标记/移除/替换）
│   │   └── report.py           # Excel 异常报告生成
│   ├── sync_to_minebase.py     # MineBase 同步 CLI 入口
│   └── sync/                   # MineBase 同步子模块
│       ├── core.py             # 同步核心
│       ├── api_client.py       # API 客户端
│       ├── db_client.py        # 数据库客户端
│       ├── file_processors.py  # 文件级处理
│       ├── row_helpers.py      # 行级辅助
│       ├── sync_engines.py     # 同步引擎
│       └── constants.py
├── gui/                        # Flet 桌面 GUI（保留，可独立运行）
│   ├── main.py                 # 组装页面 + 日志初始化
│   ├── logic.py                # 按钮事件绑定 + 后台任务调度
│   ├── theme.py / utils.py / log_system.py
│   └── components/             # 13 个组件模块（batch/common/config/ledger/oil_ledger/sync_minebase/...）
├── tauri_bridge.py             # JSON-RPC over stdio 服务端（GUI 入口）
├── tauri_bridge.spec           # PyInstaller 打包配置
├── main.py                     # Python 入口脚本
├── public/fonts/MiSansVF.ttf   # 字体资源
├── assets/                     # 应用图标（多尺寸）
├── pyproject.toml              # Python 项目配置（声明 license=Apache-2.0）
├── package.json                # Node.js 项目配置
├── vite.config.ts              # Vite 构建配置
├── tauri.conf.json             # Tauri 应用配置
├── tsconfig.json / tsconfig.node.json
├── config.json                 # 持久化默认配置（提交 Git）
├── config.user.json            # 用户覆盖配置（gitignore，含凭据）
├── tests/                      # pytest 测试（37 个文件，747 个用例）
├── .github/workflows/
│   ├── ci.yml                  # push/PR → 自动跑测试 + 类型 + Rust 检查
│   ├── build-tauri.yml         # CI 通过 → Tauri 桌面构建（macOS + Windows）
│   ├── build-flet-client.yml   # CI 通过 → Flet 桌面构建（macOS + Windows）
│   └── cleanup-artifacts.yml   # 手动清理旧 artifacts
├── LICENSE                     # Apache License 2.0
└── NOTICE                      # 依赖归属声明
```

---

## ⚙️ 配置说明

项目采用双配置文件机制：

- **`config.json`**：系统默认配置，提交到 Git，包含设备映射、班次名称等公共设置。
- **`config.user.json`**：用户覆盖配置（已 gitignore），包含数据库凭据、工作效率表头映射等敏感/个性化设置。`load_config()` 运行时自动合并两者（user 覆盖 default）。

**`config.json` 主要配置项：**

| 配置项 | 说明 |
|--------|------|
| `device_load_map` | 设备型号 → 装载量（方）映射，用于生产数据计算 |
| `device_load_map_old` | 旧版装载量映射（历史兼容） |
| `default_year` / `default_month` | 默认年月参数 |
| `shift_mapping` | 班次名称映射（中/蒙文 → 英文） |
| `worktime_header_apply` | 是否应用自定义表头映射 |
| `user_config_default` | 用户配置默认值（`file_keywords`） |

**`config.user.json` 主要配置项：**

| 配置项 | 说明 |
|--------|------|
| `user_config.database` | 数据库连接参数（`db_type/host/port/name/user/password`） |
| `user_config.worktime_header_mapping` | 工作效率表自定义表头映射（支持位置模式和模糊匹配） |
| `user_config.file_keywords` | 各报表文件识别关键字 |
| `anomaly_detection` | 异常值检测配置（阈值、σ/百分位参数、处理规则） |
| `minebase.mode` | MineBase 同步模式：`api` 或 `database` |
| `minebase.api` | API 模式连接参数（`url/username/password`） |
| `minebase.database` | 数据库直连参数（`host/port/database/user/password`） |

> **⚠️ 安全说明**：`minebase` 下的 `password` 字段通过系统 Keychain 加密存储（macOS Keychain / Windows Credential Manager），配置文件中仅保存哨兵值 `__keyring__`。首次启动 Tauri GUI 时自动将残留明文密码迁移到 Keychain；若 Keychain 不可用，密码以明文保留在 `config.user.json` 中作为回退。

> **⚠️ 行为说明**：GUI 中"应用当前配置"仅更新运行时内存（`apply_device_load_map()`），"保存配置"才会写回文件（`update_device_load_map()`）。

---

## 🧩 架构设计

### 三层架构

```
┌─────────────────────────────────────────┐
│          Tauri GUI 前端（React/TS）       │  展示层
├─────────────────────────────────────────┤
│          Rust 壳进程 + Python sidecar     │  桥接层
├─────────────────────────────────────────┤
│          Python 处理引擎（func/）          │  业务层
└─────────────────────────────────────────┘
```

- **展示层**（`src/` + `gui/`）：React + TypeScript（Tauri GUI）或 Flet 桌面 GUI，负责 UI 控件创建、用户输入收集、日志渲染。不含业务逻辑。
- **桥接层**（`src-tauri/` + `tauri_bridge.py`）：Rust 管理 Python sidecar 生命周期；`tauri_bridge.py` 实现 JSON-RPC over stdio 协议。
- **业务层**（`func/`）：Excel 解析、数据提取、配置管理、日志。CLI 与 GUI 共享同一套处理逻辑。

### 独立处理器

各 `excel_*.py` 模块相互独立，各自解析特定报表结构，不共享统一领域模型。新增处理模块时：

1. 在 `func/` 下编写处理函数，使用 `logging` / `get_logger()` 打日志；
2. 在 `gui/components/` 增加输入控件（Flet）或在 `src/components/pages/` 增加页面（React）；
3. 在 `gui/logic.py` 中接入处理函数（Flet），或在 `tauri_bridge.py` 注册新方法（Tauri）。

### 统一日志

`func/logger.py` 提供 `logging` + `get_logger()`，CLI 直接输出控制台，GUI 通过 `QueueHandler`（Flet）或 JSON-RPC 事件（Tauri）推送到页面日志列表。新增处理逻辑请使用 `logging` 而非 `print()`。

### 设备台账与油品台账

- `func/equipment_ledger.py` 支持标准名称、别名、前缀、`rapidfuzz` 相似度匹配，用于跨报表设备名称归一化。生产数据处理时，若同时存在"矿卡名称"和"挖机名称"列，匹配结果会自动添加后缀区分。
- `func/oil_ledger.py` 管理油品编码与名称映射。

### 异常值检测

`func/anomaly/` 提供统一的异常值检测与处理框架，在各处理器去重后自动调用：

**检测方式：**
- **绝对阈值**：用户配置的 min/max 范围（如油耗 > 10000）
- **σ 异常**：基于当批数据的统计离群检测（默认 3σ）
- **百分位异常**：基于当批数据的极端值检测（默认 P1/P99）
- **`__all_numeric__` 模式**：工时数据专用，自动对所有数值列统一检测（默认 0-720）

**处理模式（四选一）：**
- 输出报告：生成 `异常报告_{数据类型}.xlsx`（含汇总 + 明细）
- 标记异常值：新增「异常值」(bool) +「异常值原因」列
- 过滤异常值：移除异常行
- 处理异常值：按用户配置的默认值替换

数据处理、批量处理、数据同步三个入口均支持异常检测开关。用户可在配置界面按数据类型编辑阈值和默认值。

### MineBase 同步

`func/sync_to_minebase.py` 提供 MineBase 同步 CLI 入口，子模块位于 `func/sync/`：
- `api_client.py` / `db_client.py` — API 与数据库两种连接模式
- `file_processors.py` / `row_helpers.py` — 文件级与行级数据处理
- `sync_engines.py` — 同步引擎核心
- `core.py` / `constants.py` — 编排与常量

---

## 🧪 测试

```bash
# 运行全部测试（887 个用例）
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

**测试覆盖范围（38 个测试文件）：**

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_gui_components.py` | GUI 组件行为、布局、按钮交互 |
| `test_config_loader.py` | 配置读写落盘、默认值合并、运行时配置 |
| `test_logic_helpers.py` | GUI 逻辑辅助函数 |
| `test_excel_merger.py` / `test_table_merge.py` | Excel 合并与表内合并聚合 |
| `test_logger.py` / `test_log_consumer.py` | 日志格式化、队列分发 |
| `test_ledger_mapping.py` / `test_ledger_match_improvements.py` | 设备台账匹配与后缀 |
| `test_oil_ledger.py` | 油品台账管理 |
| `test_string_utils.py` | 字符串清理工具 |
| `test_path_traversal.py` | 路径遍历安全校验 |
| `test_excel_*.py` / `test_excel_*_fix.py` / `test_excel_*_progress.py` | 各类 Excel 处理模块 |
| `test_excel_handles.py` | Excel 句柄管理 |
| `test_excel_formatter.py` | 输出格式化 |
| `test_excel_batch.py` / `test_batch_progress_fix.py` | 批量处理 |
| `test_excel_utils.py` / `test_excel_utils_fix.py` | Excel 工具函数 |
| `test_gui_batch_progress.py` | GUI 批量进度显示 |
| `test_user_config_section.py` | 用户配置面板 |
| `test_production_config_flow.py` / `test_production_model_match.py` | 生产配置与模型匹配 |
| `test_tab_switching.py` / `test_drag_resize.py` | Tab 切换与拖拽 |
| `test_secret_store.py` | Keychain 凭证存储、密码迁移、故障回退 |
| `test_tauri_bridge.py` | Tauri RPC 方法、连接测试、启动迁移 |
| `test_orchestration.py` | 多报表编排处理 |
| `test_sync_to_minebase.py` / `test_sync_file_processors.py` | MineBase 同步 |
| `test_header_mapping_unified.py` | 表头映射统一逻辑 |
| `test_hidden_rows.py` | 隐藏行/列检测、过滤与索引映射 |
| `test_anomaly.py` | 异常值检测（阈值/σ/百分位/过滤/标记/报告，88 个用例） |

前端测试在 `src/test/` 下，使用 Vitest + Testing Library，覆盖 `LogPanel`、`Sidebar`、`Toast`、`useLastDirectory`、`usePythonBridge`。

---

## 📦 构建桌面应用

### 自动构建（推荐）

CI 通过后自动触发桌面应用构建：

- **Tauri**：macOS arm64 + Windows x64 → `.dmg` / `.exe`
- **Flet**：macOS + Windows → 独立安装包

触发条件：push 到 `main` 或 `releases/*` 分支，且 CI 全部通过。
详见 `.github/workflows/build-tauri.yml` 和 `.github/workflows/build-flet-client.yml`。

### 本地构建

```bash
# Tauri（推荐）
uv run pyinstaller tauri_bridge.spec --clean --noconfirm
pnpm tauri build

# Flet
uv run flet build macos   # macOS
uv run flet build windows # Windows
```

### 手动触发构建

在 GitHub Actions 页面选择 `Build Tauri App` 或 `Build Flet App` workflow，点击 `Run workflow`。

---

## 📋 更新日志

### v1.3.0 · 2026-07-19

- 🆕 异常值检测与处理模块（`func/anomaly/`）：支持绝对阈值、σ 异常、百分位三种检测方式
- 四种处理模式：输出报告、标记异常值（新增「异常值」+「异常值原因」列）、过滤异常值、处理异常值（按默认值替换）
- 工时数据 `__all_numeric__` 模式：自动对所有数值列统一检测（默认 0-720 范围）
- 数据处理、批量处理、数据同步三个入口均集成异常检测开关
- 用户配置界面：按数据类型编辑阈值和默认值，支持 σ 倍数和百分位范围全局设置
- Flet GUI 和 Tauri 前端均提供异常检测控件（开关 + 报告 + 三选一模式）
- 处理日志显示来源表和处理方式（如 `[油耗信息] 检测到 3 个异常值 → 异常值已标记`）
- GUI 布局优化：批量处理按功能分组为 module_card，数据同步移除多余分割线改为 2 列布局
- 新增 88 个异常检测单元测试 + 7 个配置测试，总计 887 个测试用例

### v1.2.0 · 2026-07-11

- 🆕 维修记录处理模块：从出勤统计表批注自动提取维修记录，经台账匹配和故障分类后生成含 8 个统计 sheet 的 Excel 报告
- 维修记录去重：基于（日期 + 设备名称 + 维修工时 + 批注）四字段去重，避免重复数据污染统计
- 维修分类配置管理（Flet GUI）：支持从 Excel 导入、导出模板、导出默认配置、恢复默认
- 维修报告结构重构：全周期设备型号故障汇总、大类统计、小类统计等 8 个 sheet
- 百分比计算修复：修复维修报告中部分占比列数值错误的问题
- 年份选择范围统一扩大到 ±30 年（Flet + Tauri）
- Tauri 界面文件选择器改进：生产/工时/维修模块增加文件夹浏览按钮，所有浏览按钮统一为图标样式
- Tauri 批量处理年/月改为下拉列表选择
- 修复 flet 新版 `FilePickerResultEvent` 废弃导致的测试失败

### v1.1.0 · 2026-07-03

- ✨ 跳过隐藏行 / 跳过隐藏列独立开关（`--skip-hidden-rows` / `--skip-hidden-cols`，`--skiphidden` 向后兼容）
- 支持所有处理模块：油耗、电耗、工时、生产、合并、批量处理、数据同步
- 数据同步模块默认开启「跳过隐藏行」
- 柴油报表隐藏日期列场景：块感知日期 ffill，避免隐藏列移除后数据丢失
- 工时模块支持文件/文件夹自动识别（GUI 输入框可直接粘贴文件夹路径）
- `excel_worktime_multifile.py` 重构：对齐 `excel_worktime.py` 接口，支持隐藏行列、表头映射、return_sheets
- 智能表头检测：隐藏行移除后自动修正行号/列号偏移
- 新增 `get_hidden_indices()` / `filter_hidden_from_df()` / `adjust_index_for_hidden()` 工具函数
- 新增 16 个单元测试（`test_hidden_rows.py`），总计 747 个测试用例

### v1.0.0 · 2025-06-19

- 🎉 首个正式版本
- Tauri v2 桌面应用（macOS arm64 / Windows x64 & arm64）
- React 前端 + Python sidecar（JSON-RPC over stdio）
- 7 个 Excel 报表处理模块
- 设备台账 / 油品台账 / 模糊匹配
- Keychain 密码加密存储
- GitHub Actions 自动构建（CI 通过后触发）+ artifacts 清理

---

## 📄 许可证

[Apache License 2.0](LICENSE)
