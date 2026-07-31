# ⛏️ MiningProcessor

> 矿山运营 Excel 报表批量处理工具

<p>
  <img src="https://img.shields.io/badge/version-v2.1.2-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/Python-≥3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square" alt="license" />
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey?style=flat-square" alt="platform" />
  <img src="https://img.shields.io/badge/Tauri-v2-FFC131?style=flat-square&logo=tauri&logoColor=black" alt="tauri" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="react" />
  <img src="https://img.shields.io/badge/tests-1054%20passed-brightgreen?style=flat-square" alt="tests" />
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
| `excel_maintenance.py` | — | 维修记录提取、规则分类及可选 ML 辅助识别 | 出勤统计表文件或文件夹 | `维修记录统计.xlsx` |
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

# 启用 Git hooks（push 前自动运行测试）
git config core.hooksPath hooks
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

# 用 LLM checkpoint 作为补充监督数据训练维修分类器
uv run maintenance-train <维修明细.xlsx> \
  --llm-checkpoint <LLM标注.xlsx.checkpoint.jsonl> \
  --llm-input <待确认记录.xlsx> \
  --llm-record-id-column 原始记录ID \
  --output models/maintenance_classifier.joblib \
  --llm-min-confidence 0.90 \
  --llm-min-agreement 0.75

# 维修记录处理中禁用 ML 二级识别（默认开启且只回填规则待确认项）
uv run python func/excel_maintenance.py <输入文件或文件夹> --no-ml

# 对抽取子集标注时，用稳定 ID 保证 checkpoint 可映射回完整原始表
uv run maintenance-llm-label <待确认记录.xlsx> \
  --model <模型名> \
  --category-column 新版大类 \
  --record-id-column 原始记录ID

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
│   ├── theme.py / utils.py      # 主题与 GUI 辅助函数
│   ├── log_broker.py            # 进程级日志分发与页面订阅
│   ├── log_system.py            # Flet 页面日志状态与单写者渲染
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
├── hooks/                      # Git hooks（push 前自动运行测试）
│   └── pre-push
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

`func/logger.py` 提供 `logging` + `get_logger()`，CLI 直接输出控制台。Flet 由进程级 `GuiLogHandler` 将记录广播给各页面订阅，每个页面通过单一异步刷新入口批量更新日志列表。Tauri 使用包含序号、时间、来源和异常详情的结构化事件，Rust 通过有界通道批量转发，React 再按 50ms 窗口合并渲染。新增处理逻辑请使用 `logging` 而非 `print()`。

Flet 日志面板保留最近 5000 条历史记录、最多渲染 1000 个控件。用户上翻时会暂停自动跟随；队列高峰时优先保留 WARNING/ERROR。界面中的异常只显示根因，导出的日志保留完整 traceback 供诊断。

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
# 运行全部测试（935 个用例）
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

### 版本号管理

项目版本号统一由 `scripts/bump_version.py` 管理，以 `pyproject.toml` 为唯一真相源，自动同步到：

- `package.json`（Node.js / Flet 前端）
- `src-tauri/tauri.conf.json`（Tauri 应用配置）
- `src-tauri/Cargo.toml`（Rust crate）

```bash
# 查看当前版本，同步所有文件
uv run scripts/bump_version.py

# 升级版本号（自动同步四份文件）
uv run scripts/bump_version.py --bump patch   # 1.5.0 → 1.5.1
uv run scripts/bump_version.py --bump minor   # 1.5.0 → 1.6.0
uv run scripts/bump_version.py --bump major   # 1.5.0 → 2.0.0

# 指定版本号
uv run scripts/bump_version.py 1.3.1

# 预览变更，不实际写入
uv run scripts/bump_version.py --bump minor --dry-run
```

---

## 📋 更新日志

### v2.1.1 · 2026-07-31

- ⚡ **工时处理空行过滤优化**
  - 新增 `drop_empty_device_name()` 共享函数（`excel_utils.py`），过滤设备名称为空（NaN / 纯空白）的行
  - `split_day_night_shifts()` 前移除全空行（`dropna(how="all")`），避免干扰白班/夜班分界检测
  - 表头映射后、插入日期列前，尽早过滤设备名称为空的行，防止垃圾数据进入后续流程
  - `pd.concat()` 后二次兜底过滤，拦截合并时可能混入的空设备名行
- ✅ **测试覆盖**
  - 新增 9 个 `drop_empty_device_name` 单元测试，覆盖 NaN、空白字符串、列不存在、不可变性、索引重置等场景

### v2.1.0 · 2026-07-30

- 🏗️ **架构重构：Flet / Tauri 双前端统一调度层**
  - `process_single()` 成为 Flet 和 Tauri 的唯一调度入口（调用率从 0% → 100%），消除 ~260 行重复调度代码
  - `get_output_path()` 统一 6 种模块的输出路径计算，修复 Flet 侧硬编码 `'合并产量.xlsx'` 的不一致问题
  - `AnomalyConfig.build_from_ui()` 统一异常值检测配置构建，修复 Tauri 侧返回 `None` 而非 `AnomalyConfig(enabled=False)` 的类型不一致
- 🏗️ **前端共享组件库**（Tauri `src/lib/`）
  - `ui-components.tsx`：提取 ToggleSwitch、StyledToggle、ChipToggle、PathInput、ConfirmDialog、Collapsible、SectionDivider 7 个共享组件
  - `icons.tsx`：64 个 SVG 图标集中管理，消除 10+ 文件中的内联 SVG 副本
- 🏗️ **大文件拆分**
  - `gui/components/user_config.py`（1,846 行）→ `user_config/` 包（8 个子模块，最大 477 行）
  - `UserConfigPage.tsx`（1,999 行）→ `user-config/` 目录（8 个子组件，最大 433 行）
- 🐛 **Bug 修复**
  - 设备装载量配置"应用"按钮现在同时写入磁盘（之前只更新运行时内存）
  - `tauri_bridge.py` 中 LLM API key 掩码从硬编码 `"***"` 改用 `LLM_KEY_MASK` 常量
  - `tauri_bridge.py` 中 `load_ledger_file_columns` / `load_oil_ledger_file_columns` 100% 重复代码合并为 `_load_excel_columns`
- 🔧 **代码质量**
  - `gui/logic.py` 中 `on_test_db_connection` / `on_test_api_connection` 提取 `_run_connection_test` 共享助手
  - `modules.py` 98 行内联异常值检测控件替换为 `create_anomaly_controls()` 共享工厂
  - `sync_minebase.py` 本地年/月选项生成改用共享 `year_options()` / `month_options()`
  - `common.py` 中 6 处 inline `try/except` 统一为 `safe_update()`
- 📊 测试用例从 996 增加到 1,054 个，测试文件从 38 增加到 43 个

### v2.0.3 · 2026-07-28

- 🆕 油耗模块新增"过滤零小时数"和"过滤零运行小时数"开关：发动机小时数或运行小时数为 0 / 空时自动过滤（Flet / Tauri / CLI）
- 🆕 生产模块运行数据新增 4 个过滤开关：过滤零小时仪表、零公里仪表、零运行小时数、零运行里程（Flet / Tauri / CLI）
- 🎨 Tauri 批量处理：过滤开关移入高级选项折叠面板（Toggle switch 风格），参数配置区分台账匹配与 Excel 选项两组
- 🎨 Tauri 单文件处理：过滤开关改为紧凑 checkbox 样式（参考文件合并模块）
- 🎨 Flet 批量处理：过滤开关独立为"数据过滤"栏目，油耗/生产两组用分割线分隔
- 🎨 Tauri 数据同步：年份/月份/表头起始行统一 `h-9` 高度，消除 select 与 input 高度不一致
- 🐛 Tauri 设备台账搜索框：修复文字与搜索图标重叠（CSS 优先级问题）
- 🧪 新增 15 个过滤功能单元测试（fuel 7 个 + production 8 个）

### v2.0.2 · 2026-07-28

- 🆕 油耗模块新增"过滤零小时数"开关（Flet / Tauri / CLI）：勾选后发动机小时数开始或结束为 0 或为空的记录将被过滤
- 🆕 油耗模块新增"过滤零运行小时数"开关（Flet / Tauri / CLI）：勾选后运行小时数为 0 或为空的记录将被过滤
- 🎨 两个新开关位于油耗模块卡片内部，而非全局选项区，更符合模块专属配置的直觉

### v2.0.1 · 2026-07-28

- 🆕 文件合并新增"兼容表头"开关（Flet / Tauri / CLI `--tolerant-header`）：勾选后表头不一致的文件也能合并，缺失列自动填空；未勾选时保持原有严格校验行为
- 🎨 Tauri 默认窗口高度从 800 提升至 950，日志面板默认高度从 180 提升至 280

### v2.0.0 · 2026-07-28

- 🆕 建立面向露天矿山工程机械的维修分类体系：20 个大类、102 个小类，每条记录只保留一个大类/小类；主发电机、轮马达和 IGBT 明确归入电驱动系统，举升缸、转向缸、悬挂缸统一归入液压系统
- 🆕 新增字符级 TF-IDF + 分层线性分类器，对规则仍判为“其他/待确认”的故障记录进行高置信度二级识别；规则结果始终优先
- 🆕 Flet、Tauri 和 CLI 均支持启用/关闭机器学习辅助识别，维修明细增加“分类方式”和“分类置信度”
- 🆕 新增 `maintenance-llm-label`：支持 OpenAI 兼容接口、每批最多 50 条、checkpoint 断点续标、稳定记录 ID，以及从 `.maintenance_llm.env` 读取 URL、API Key 和模型名
- 🆕 新增 `maintenance-train`：可合并重复 LLM 标注、按记录与内容进行置信度加权投票，并以高置信度共识标签补充规则训练集
- 🆕 桌面安装包内置当前生效模型；Flet、Tauri 和 CI 构建流程增加模型存在性、可加载性及打包完整性检查
- 🎯 最终模型使用 47,630 条训练样本、覆盖 84 个可训练分类；留出集准确率 83.99%，Macro F1 80.48%，安全接收准确率 97.84%
- 🔧 全量版本号更新到 v2.0.0，Python 全量测试 996 个通过

### v1.5.0 · 2026-07-27

- 🆕 油耗模块动态表头检测：自动查找表头锚点（"Д/д" / "Парк дугаар"）、日期行、油品品牌行（НИК / IC IC / Primary），不再依赖固定行号，兼容更多报表结构
- 🆕 旧格式 `.xls` 文件支持：维修记录提取和文件发现支持 `.xls` 格式（通过 xlrd 适配器模拟 openpyxl 接口），隐藏行列检测对 `.xls` 自动跳过
- 🆕 页面关闭时终止后台任务：关闭 Flet / Tauri 窗口自动取消正在运行的批量处理任务，生产数据处理支持中途取消（cancel_event 透传到多线程处理循环）
- 🆕 批量 / 生产处理汇总 UI：Tauri 前端处理完成后展示成功/失败模块列表及警告信息（如未匹配装载量型号），Flet GUI 生产处理后显示文件统计
- 🆕 逐列异常检测开关持久化：从各页面运行时 UI 移除，统一迁移到用户配置页面集中管理，所有 GUI 入口从 `config_loader` 读取，配置更清晰
- 🆕 用户配置页面增强（Flet + Tauri）：新增逐列异常检测开关管理界面
- 🐛 油耗模块班次识别改进：改为扫描所有表头行（不再固定第 3 行），燃油类型增加关键字扫描后备机制
- 🐛 油耗模块移除无油品类型的空记录，避免无效数据污染输出
- 🐛 Flet 日志面板重构：进程级 Broker 隔离多页面订阅，页面使用单一异步刷新入口消除控制树竞态；支持上翻暂停跟随、有界渲染、高峰期优先保留警告/错误，日志级别筛选默认值为 INFO
- 🐛 Tauri 日志链路重构：保留完整 traceback，Rust 使用有界批量转发，React 日志状态按 50ms 合并并限制渲染窗口；支持上翻暂停跟随、键盘调整高度和可访问级别标签
- 🐛 生产处理摘要（_processing_summary）：process_folder 返回 warnings 和 errors 列表，调用方可获取未匹配型号等警告
- 🎨 Tauri AnomalyPanel 简化：移除运行时逐列开关 UI（ColumnToggles），只保留开关和模式选择
- 🎨 用户配置页面文件关键字区块默认折叠，减少视觉干扰
- 🎨 ledger_match.py、maintenance_classification.py 代码精简
- 🔧 全量版本号更新到 v1.5.0（pyproject.toml / package.json / tauri.conf.json / Cargo.toml）
- 🧪 Python 测试用例从 887 个增加到 939 个，React 45 个，Rust 2 个

### v1.3.1 · 2026-07-20

- 🐛 GUI 错误日志简化：ERROR 级别日志不再显示完整 Python traceback，只展示根因异常消息（如 `Path does not exist: xxx.xlsx`）
- Tauri 前端 RPC 错误消息同步优化：去掉 traceback 和文件位置，只返回根因文字
- 完整 traceback 仍通过 `logger.exception()` 保留在后端日志，不影响调试排查
- 🆕 统一版本号管理：`scripts/bump_version.py` 以 `pyproject.toml` 为唯一真相源，一次修改同步 `package.json`、`tauri.conf.json`、`Cargo.toml`

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
