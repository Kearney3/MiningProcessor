# AGENTS.md

本文件为 MiningProcessor 仓库开发指引。

## 项目概览

项目包含两类入口：

- **CLI**：处理 Excel 报表或批量文件夹，结果写回输入目录。
- **Tauri 桌面应用**：React + TypeScript 前端通过 Rust 宿主连接 Python sidecar。

Excel 解析和业务处理位于 `func/`。Tauri 通信由 `tauri_bridge.py` 提供 JSON-RPC over stdin/stdout；`src-tauri/` 管理 sidecar 生命周期、日志转发和桌面打包。

## 常用命令

```bash
# 安装 Python 依赖
uv sync --dev

# 安装前端依赖
pnpm install

# 启动 Tauri 开发环境（Python bridge、Vite、桌面窗口）
pnpm tauri dev

# Python 测试
uv run pytest

# React 前端测试
pnpm exec vitest run

# 前端生产构建
pnpm build
```

CLI 示例：

```bash
uv run fuel <输入文件> --year 2025
uv run electrical <输入文件> --year 2025
uv run production <输入文件或文件夹>
uv run worktime <输入文件或文件夹> --year 2025 --month 1
uv run merge <输入文件夹> <关键字>
```

## 架构与修改位置

### 1. 业务处理在 `func/`

`func/` 包含 Excel 处理器、配置、日志、台账、同步和异常检测。修复数据处理问题时，先定位这里的实现，不要把 Excel 解析搬进 React 页面或 Rust 宿主。

`func/orchestration.py` 提供 `process_single()`、输出路径和台账后处理等共用编排。各处理器仍然独立，新增报表类型时放在 `func/` 的合适模块，再从 CLI 或 Tauri bridge 调用。

### 2. Tauri 前端与 Python 通信

- `src/`：React 页面、共享组件、国际化和前端测试。
- `src/hooks/usePythonBridge.ts`：前端调用与事件订阅。
- `src/lib/types.ts`：RPC 和进度事件的 TypeScript 类型。
- `tauri_bridge.py`：通过 `@_register("method_name")` 注册 Python RPC；stdout 仅用于协议响应，日志写入 stderr。
- `src-tauri/src/python_bridge.rs`：sidecar 子进程、并发请求、取消和 stdout/stderr 读取。
- `src-tauri/src/lib.rs`：Tauri commands、sidecar 启动和日志事件转发。

新增或修改功能时，保证 RPC 方法名、参数、返回值和事件结构在 Python bridge、React 调用和类型定义之间一致。长任务应支持进度事件；支持取消的任务需连接 Rust cancel command 与 Python cancellation token。

### 3. 日志与错误

处理逻辑使用 `logging` / `get_logger()`，不要用 `print()` 污染 bridge stdout。CLI 日志输出到控制台；Tauri bridge 将日志结构化写入 stderr，由 Rust 转发给 React 日志面板。

前端错误只显示根因消息。后端使用 `logger.exception()` 保留完整 traceback 供诊断。

### 4. 配置

- `config.json`：提交到 Git 的系统默认配置。
- `config.user.json`：用户覆盖配置，已 gitignore，可保存敏感及个性化设置。
- `func/config_loader.py` 的 `load_config()` 合并配置，用户配置覆盖默认配置。
- `apply_device_load_map()` 只更新当前进程内存；`update_device_load_map()` 才会写入配置文件。
- 凭据加密由 `func/secret_store.py` 负责。不要让 bridge 把密文或密钥传给前端。

### 5. 台账与异常检测

设备、油品和型号台账分别由 `func/equipment_ledger.py`、`func/oil_ledger.py`、`func/model_ledger.py` 管理。跨报表匹配优先复用这些模块及 `func/ledger_postprocess.py`，不要另造一套名称匹配规则。

`func/anomaly/` 提供规则、检测、过滤和异常报告。改处理器或入口时，保留现有 `anomaly_config` 传递和异常明细返回行为。

## 测试与验证

- Python 处理器/配置/桥接：在 `tests/` 查找对应 pytest 文件。
- React 页面和 hooks：在 `src/test/` 查找对应 Vitest 文件。
- Rust 宿主：检查 `src-tauri/src/` 内的单元测试。

改 `src/`、`src-tauri/`、`tauri_bridge.py`、`func/config_loader.py` 时，优先运行相关测试和构建命令。仓库使用 `ruff`，配置位于 `pyproject.toml`。

## Git 提交规范

提交标题使用英文 Conventional Commits：`type(scope): short description`。type 使用 `feat`、`fix`、`docs`、`style`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`、`revert` 或 `merge`；scope 小写；描述以英文字母开头，最长 120 字符且不以句号结尾。

提交检查由 `commitlint.config.mjs` 和 `hooks/commit-msg` 执行；`hooks/pre-push` 运行测试。不要使用 `git commit --no-verify` 绕过 hooks。
