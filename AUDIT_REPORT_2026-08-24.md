# MiningProcessor 项目全面审计报告

**审计日期**: 2026-08-24
**审计范围**: func/ 处理引擎、gui/ Flet GUI、tauri_bridge.py、src/ Tauri 前端、tests/ 测试、安全性、i18n
**审计方法**: 15 个并行审计 agent，覆盖代码质量、架构、安全、性能、测试、国际化 6 大维度

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| Python 源文件 | 54 个 (func/ + gui/) |
| TypeScript/React 文件 | 55 个 (src/) |
| Tauri Bridge | 1 个 (1619 行) |
| 测试文件 | 68 个 (53 Python + 15 TypeScript) |
| 测试用例 | 1,355 个 |
| **总发现数** | **~280 项** |
| CRITICAL | 8 项 |
| HIGH | 45 项 |
| MEDIUM | 120 项 |
| LOW | 107 项 |

**整体健康度评分: 6.5/10**

- 核心业务逻辑正确，测试覆盖尚可（Python 69%，Tauri 32%）
- 主要风险集中在：超大文件维护困难、配置缓存竞态条件、翻译质量严重不足、Tauri 前端测试缺口大
- 安全基线良好（参数化 SQL、SSRF 防护、加密存储），但有若干需加固的点

---

## 一、关键发现（CRITICAL）

### C1. `func/label_maintenance_with_llm.py` — 1740 行，超出限制 2 倍
- **文件**: `func/label_maintenance_with_llm.py:1`
- **问题**: 文件包含 LLM 客户端、批处理编排、checkpoint 管理、CLI 入口等 6+ 个不相关关注点
- **影响**: 开发者无法在工作记忆中容纳完整文件；`label_file`(196 行) 和 `process_maintenance_llm`(369 行) 存在大量重复的批处理编排逻辑
- **修复**: 拆分为 `llm_client.py`、`batch_orchestrator.py`、`checkpoint.py`、`cli.py` 四个模块

### C2. `func/config_loader.py` — 1257 行，混合 8+ 个不相关领域
- **文件**: `func/config_loader.py:1`
- **问题**: 路径解析、配置加载/保存、设备装载量映射、异常检测配置、LLM 配置、台账缓存、MineBase 配置、列映射全部在一个文件
- **影响**: 不同功能的修改频繁产生合并冲突
- **修复**: 按领域拆分为 `config_core.py`、`config_device.py`、`config_llm.py`、`config_minebase.py`、`config_cache.py`

### C3. `config_loader.load_config()` 返回可变缓存引用
- **文件**: `func/config_loader.py:294`
- **问题**: `load_config()` 直接返回 `_config_cache` 的引用，任何调用者的修改都会污染缓存
- **影响**: `get_daily_report_config()` 中的 `result.pop()` 和 `formulas[key] = ...` 已经在破坏缓存
- **修复**: 返回 `copy.deepcopy(_config_cache)`

### C4. `config_loader._deep_merge` 浅拷贝导致嵌套对象共享引用
- **文件**: `func/config_loader.py:225`
- **问题**: `result = dict(base)` 只做浅拷贝，未被 override 覆盖的嵌套 dict/list 与原始对象共享引用
- **影响**: 与 C3 叠加，放大缓存污染风险
- **修复**: 使用 `result = copy.deepcopy(base)`

### C5. `sync/db_client.py` LIKE 查询未转义通配符
- **文件**: `func/sync/db_client.py:48`
- **问题**: `equip_name` 中的 `%` 和 `_` 未转义，导致 LIKE 查询匹配错误设备
- **影响**: 设备名含 `_`（如 `Model_X`）时会匹配到不相关记录
- **修复**: 在构造 LIKE 模式前转义 `%` → `\%`、`_` → `\_`

### C6. `sync_engines.sync_via_db` 全部回滚
- **文件**: `func/sync/sync_engines.py:515`
- **问题**: 单行失败导致整个数据类型的已成功行全部回滚
- **影响**: 大批量同步时，一行脏数据导致整个批次丢失
- **修复**: 改为逐行 commit 或使用 savepoint 部分回滚

### C7. `ledger_match.py` 挖掘机匹配硬编码 `device_id=None`
- **文件**: `func/ledger_match.py:196`
- **问题**: 匹配 lambda 忽略了 `id_col` 参数，始终传 `device_id=None`
- **影响**: 挖掘机的 ID 列匹配完全失效
- **修复**: 将 lambda 改为使用 `id_col` 参数

### C8. `gui/logic.py:769` — `NameError: missing_labels` 未定义
- **文件**: `gui/logic.py:769`
- **问题**: `on_batch_process()` 引用 `missing_labels`，但该变量仅在 `_log_scan_summary()` 内部定义
- **影响**: 批量处理时如果文件缺失，触发确认对话框时会崩溃
- **修复**: 将 `missing_labels` 作为 `_log_scan_summary()` 的返回值传递

---

## 二、高优先级问题（HIGH）

### 2.1 文件大小超标

| 文件 | 行数 | 限制 | 超出 |
|------|------|------|------|
| `func/label_maintenance_with_llm.py` | 1740 | 800 | +118% |
| `tauri_bridge.py` | 1619 | 800 | +102% |
| `gui/logic.py` | 1442 | 800 | +80% |
| `func/config_loader.py` | 1257 | 800 | +57% |
| `func/daily_report.py` | 1027 | 800 | +28% |
| `func/excel_tire.py` | 986 | 800 | +23% |
| `func/excel_production_enhanced.py` | 916 | 800 | +15% |
| `gui/components/ledger_match.py` | 889 | 800 | +11% |
| `func/excel_batch.py` | 842 | 800 | +5% |
| `func/excel_utils.py` | 811 | 800 | +1% |
| `src/pages/DataProcessingPage.tsx` | 1143 | 500 | +129% |
| `src/pages/LedgerMatchPage.tsx` | 964 | 500 | +93% |
| `src/pages/DataSyncPage.tsx` | 918 | 500 | +84% |
| `src/pages/LedgerPage.tsx` | 853 | 500 | +71% |

### 2.2 超长函数

| 函数 | 文件:行 | 行数 | 问题 |
|------|---------|------|------|
| `process_maintenance_llm` | label_maintenance_with_llm.py:1203 | 369 | 混合验证、批处理、取消、checkpoint、导出 |
| `build_daily_report` | daily_report.py:730 | 267 | 混合预处理、聚合、公式计算、列组装 |
| `parse_sheet` | excel_tire.py:554 | 244 | 混合表头检测、期间构建、行迭代、日期解析 |
| `on_batch_process` | gui/logic.py:656 | 218 | 混合扫描、确认对话框、执行三个阶段 |
| `label_file` | label_maintenance_with_llm.py:955 | 196 | 与 process_maintenance_llm 大量重复 |
| `process_sheet1` | excel_production_enhanced.py:213 | 191 | 混合表头检测、列匹配、行迭代、产量计算 |
| `process_folder` | excel_production_enhanced.py:695 | 183 | 混合文件收集、线程、结果聚合、异常检测 |
| `process_files` | excel_batch.py:192 | 179 | 混合模块分发、异常跟踪、日期过滤、台账匹配 |
| `_preprocess_sources` | daily_report.py:265 | 131 | 5 种数据类型重复 try/except 模式 |
| `_table_merge_and_write` | excel_batch.py:637 | 127 | 混合聚合、列对齐、左连接、输出 |

### 2.3 配置系统竞态条件

- **`update_device_load_map`** (`config_loader.py:406`): 读-改-写周期未加锁，两个并发调用者会互相覆盖
- **`update_maintenance_classifications`** (`config_loader.py:638`): 同样的竞态
- **`set_default_shift`** (`config_loader.py:440`): 同样的竞态
- **`_runtime_lock`** 仅保护 `_runtime_config` 清除，不保护文件读写

### 2.4 Tauri Bridge 输入验证缺失

以下 RPC 方法缺少必需参数验证，缺失参数时抛出 `KeyError` 而非清晰的验证错误：

| 方法 | 缺失参数 |
|------|---------|
| `process_worktime` | year, month |
| `save_config` | data |
| `save_minebase_config` | config |
| `update_device_load_map` | map_data |
| `apply_device_load_map` | map_data |
| `set_load_map_version` | version |
| `update_maintenance_classifications` | rules |
| `save_minebase_column_mapping` | mapping |
| `read_excel_sheet` | sheet |

### 2.5 翻译质量严重不足

| 文件 | 问题翻译数 | 总翻译数 | 占比 |
|------|-----------|---------|------|
| `gui/locales/en.json` | ~80 | 966 | 8% |
| `gui/locales/mn.json` | ~150 | 966 | 16% |
| `src/locales/en.json` | ~30 | 985 | 3% |
| `src/locales/mn.json` | ~100 | 985 | 10% |

典型问题翻译：`'filefile'`、`'itemExport'`、`'columnfilter'`、`'item'` — 这些是机器提取工具生成的伪翻译，不是真正的英文/蒙文。

### 2.6 Tauri 前端测试缺口

- **30/44 (68%)** Tauri 组件无测试覆盖
- 所有 13 个页面组件中仅 4 个有测试
- 所有 8 个 user-config section 中仅 1 个有测试
- 关键缺失：`UserConfigPage`、`BatchProcessingPage`、`EquipmentLedgerPage`

### 2.7 Flet GUI 核心问题

- **`_MODULE_LABELS`** 在模块导入时调用 `t()`，冻结翻译 — 语言切换对这些标签无效
- **`gui/main.py:66`** 语言切换对话框 append 到 overlay 后未移除，每次切换泄漏一个 AlertDialog
- **`gui/log_system.py:121`** `LogSystem` 独占覆盖 `page.window.on_resize`，丢弃已注册的处理器
- **`gui/logic.py:787`** `asyncio.to_thread(event.wait, 300)` 阻塞线程池线程最长 5 分钟

### 2.8 Tauri 前端架构问题

- **`App.tsx:92`** 所有 12 个页面同时渲染（`display:none`），所有 useEffect 在启动时触发
- **`usePythonBridge.ts:208,212`** 不安全的双重类型断言 `as unknown as BatchProgress`
- **无 React Error Boundary** 包裹页面组件，单个 throw 导致整个应用崩溃
- **`DataSyncPage`** 使用 30 个独立 `useState`，应改用 `useReducer`

### 2.9 同步模块健壮性

- **`db_client.py:13`** 无上下文管理器，异常时连接泄漏
- **`db_client.py:15`** `psycopg2.connect` 无 `connect_timeout`，可能挂起数分钟
- **`api_client.py:50`** 无重试逻辑处理瞬态网络错误或 5xx 响应
- **`sync_engines.py:97`** 轮询循环最长运行 83 分钟，无退避或可配置超时
- **`file_processors.py:109`** `except Exception` 捕获了 `KeyboardInterrupt`/`SystemExit`

### 2.10 代码重复

| 重复模式 | 涉及文件 | 影响 |
|---------|---------|------|
| 台账缓存 CRUD 三重复制 | config_loader.py:1044-1158 | ~115 行重复代码 |
| `label_file` vs `process_maintenance_llm` | label_maintenance_with_llm.py | 批处理编排重复 |
| 工时后处理管道 | excel_worktime.py + excel_worktime_multifile.py | ~40 行重复 |
| 三个模块处理器相同 try/except 循环 | excel_batch.py:90 | 燃油/电力/工时 |
| FilePicker 创建模式 12+ 处重复 | gui/components/ 多文件 | 维护负担 |
| 7 个 user-config section 重复 save/reload/reset 状态模式 | src/components/user-config/ | 应提取 `useConfigSection` hook |
| 18 个台账 CRUD RPC 方法 | tauri_bridge.py:1052 | 应使用工厂模式 |

---

## 三、中优先级问题（MEDIUM）

### 3.1 不可变性违反（Mutation）

项目编码规范明确要求不可变模式，但以下位置存在就地修改：

| 位置 | 修改内容 |
|------|---------|
| `label_maintenance_with_llm.py:1119` | DataFrame 就地添加 LLM 结果列 |
| `daily_report.py:423` | `_canonical_device` 就地修改 attrs dict |
| `daily_report.py:663` | 聚合 bucket 就地修改 |
| `excel_tire.py:474` | `recalculate_derived_fields` 就地修改行 |
| `excel_production_enhanced.py:290` | DataFrame 列名就地修改 |
| `excel_batch.py:251` | `anomaly_config._anomaly_counts = []` 直接设置私有属性 |
| `orchestration.py:322` | `process_single` 就地修改 anomaly_config |
| `config_loader.py:421` | `config[config_key].update(updates)` 保存前就修改 |
| `config_loader.py:924` | `updates.pop('api_key', None)` 修改调用者传入的 dict |
| `config_loader.py:734` | `get_daily_report_config` 通过 `pop()` 修改合并结果 |
| `anomaly/__init__.py:128` | `detect_and_filter` 就地修改 config |
| `gui/components/ledger_base.py:34` | `LedgerConfig` 构造后就地修改 |

### 3.2 深层嵌套（>4 层）

| 位置 | 嵌套层级 |
|------|---------|
| `label_maintenance_with_llm.py:1502` | 导出逻辑 5+ 层 |
| `daily_report.py:853` | 生产聚合循环 5+ 层 |
| `excel_tire.py:667` | 期间处理循环 5+ 层 |
| `excel_production_enhanced.py:344` | 生产列迭代 5+ 层 |
| `gui/components/llm_labeling.py:90` | 690 行函数 4+ 层 |

### 3.3 魔法数字

| 位置 | 值 | 问题 |
|------|-----|------|
| `config_loader.py:451` | `2025` | 默认年份硬编码 |
| `excel_utils.py:305` | `year=2025, month=1` | 函数签名默认值 |
| `excel_production_enhanced.py:418` | `col_device=1, col_company=2...` | 5 个硬编码列索引 |
| `excel_production_enhanced.py:508` | `50, 30` | Sheet 角色检测阈值 |
| `excel_tire.py:135` | `1900-2099` | 日期范围硬编码 |
| `maintenance_classification.py:241` | `131072` | LRU 缓存大小无说明 |
| `label_maintenance_with_llm.py:969` | `800` | max_content_chars 重复出现 3 次 |
| `tauri_bridge.py:1460` | `'1.2.0'` | ping 返回硬编码版本号 |

### 3.4 安全问题

| 严重度 | 文件:行 | 问题 |
|--------|---------|------|
| MEDIUM | `secret_store.py:68` | 硬编码回退密码短语 `'MiningProcessor-2024-secret-store'` |
| MEDIUM | `config_loader.py:268` | `config.user.json` 无限制文件权限（默认 0644） |
| MEDIUM | `tauri_bridge.py:1472` | `write_text_file` 无内容大小限制，可写任意路径 |
| MEDIUM | `tauri_bridge.py:66` | `_validate_url` 允许 DNS 重绑定攻击 |
| MEDIUM | `tauri_bridge.py:103` | `sanitize_path` 未阻止 null 字节 |
| MEDIUM | `api_client.py:44` | MineBase API 客户端未强制 HTTPS |
| MEDIUM | `label_maintenance_with_llm.py:375` | LLM 客户端未强制 HTTPS |
| MEDIUM | `maintenance_ml_classifier.py:394` | `joblib.load` 加载不受信模型可执行任意代码 |

### 3.5 性能问题

| 位置 | 问题 | 影响 |
|------|------|------|
| `sync/db_client.py` | N+1 查询（每行 3 次查询解析设备） | 大批量同步极慢 |
| `sync/sync_engines.py:482` | 逐行 INSERT 而非批量 | O(N) 数据库往返 |
| `ledger_base.py:86` | `_build_search_cache` 使用 `iterrows()` | 大台账时慢 |
| `ledger_enrichment.py:72` | 每行调用 `resolve_equipment_attributes` 无去重 | 与 `ledger_postprocess.py` 不一致 |
| `building.py:129` | 循环体内 `import calendar` | 每次迭代重新导入 |
| `anomaly/detector.py:54` | `_find_numeric_columns` 每个 `__all_numeric__` 规则重新计算 | 重复计算 |
| `extraction.py:117` | `_XlrdSheetWrapper.row_dimensions` 每次访问重建 dict | 属性访问性能差 |
| `App.tsx:92` | 所有 12 个页面同时挂载 | 启动时触发所有 bridge 调用 |
| `DataSyncPage` | 无 memoization，任何状态变化触发全量重渲染 | UI 卡顿 |
| `BatchProcessingPage` | `doProcess` useCallback 有 29 个依赖 | 依赖数组过大 |

### 3.6 Tauri 用户配置验证缺失

| Section | 缺失验证 |
|---------|---------|
| `AnomalyConfigSection` | 数值字段 sigmaN/pctLow/pctHigh 无验证，NaN 静默回退默认值 |
| `AnomalyConfigSection` | 阈值 min > max 无验证 |
| `MineBaseSection` | API 模式 url/username 为空无验证 |
| `MineBaseSection` | DB 模式 host/database/user 为空无验证 |
| `LLMConfigSection` | URL/model 为空无验证 |
| `LLMConfigSection` | API key 被遮蔽时保存发送空字符串，可能清除密钥 |
| `ColumnMappingSection` | 保存后无 reload，本地状态可能与后端不一致 |
| `ColumnMappingSection` | 使用浏览器 `prompt()` 添加映射行 |

### 3.7 取消机制不完整

以下处理器不支持取消（未使用 `_begin_cancellable_task`）：
- `process_fuel`
- `process_tire`
- `process_electrical`
- `process_merge`
- `process_maintenance`

仅 `process_production` 和 `process_maintenance_llm` 正确使用了取消模式。

### 3.8 线程安全问题

- `gui/logic.py:34` — `_active_cancel_events` 列表从异步处理器修改，从 `shutdown_tasks()` 清除，无同步
- `gui/logic.py:153` — `_btn_original_styles` 使用 `id(btn)` 作为字典键，Python GC 后会复用 ID
- `gui/components/llm_labeling.py:169` — `sample_data`、`value_options`、`columns_list` 从线程访问无锁
- `MiningDataProcessor` — `_hidden_rows`、`_hidden_cols`、`raw_start` 在 `ThreadPoolExecutor` 线程间共享无同步

---

## 四、低优先级建议（LOW）

### 4.1 日志格式

- `excel_merger.py`、`excel_worktime.py`、`excel_worktime_multifile.py` 使用 f-string 而非惰性格式化
- `logger.info(f'found {len(files)} files')` → `logger.info('found %d files', len(files))`

### 4.2 测试质量

- 5 个测试无断言（仅验证不崩溃）
- 16 处 `time.sleep()` 导致测试不稳定
- 11 处硬编码 `/tmp/` 路径
- 8 处精确浮点比较应使用 `pytest.approx()`
- `conftest.py` 仅 3 个 fixture，15+ 文件重复定义 `ROOT`

### 4.3 无障碍（Accessibility）

- `Sidebar.tsx` 11 个 SVG 图标缺少 `aria-hidden="true"`
- `LedgerMatchPage` ~15 个按钮缺少 `aria-label`
- 多个模态框缺少焦点陷阱和 Escape 键处理
- 多处使用 `text-slate-400`（对比度 ~3.0:1，低于 WCAG AA 的 4.5:1）

### 4.4 依赖管理

- `scikit-learn>=1.9.0`（~30MB）作为生产依赖，仅被可选 ML 分类器使用
- `psycopg2-binary>=2.9` 作为生产依赖，仅 MineBase DB 直连模式使用
- `python-calamine>=0.1.0` 无上界（pre-1.0 包）

### 4.5 其他

- `tauri_bridge.py:1460` — ping 返回硬编码版本 `'1.2.0'`，应从 `pyproject.toml` 读取
- `tauri_bridge.py:1272` — 错误响应格式不一致（3 种模式）
- `tauri_bridge.py:580` — `_CANCEL_FILE` 使用固定路径，多实例会冲突
- `tauri_bridge.py:1591` — 无优雅关闭，SIGTERM 时任务被丢弃
- `tauri_bridge.py:1547` — 长时间运行任务无超时，卡住的任务永久阻塞执行器
- `string_utils.py:20` — `_ZERO_WIDTH` 正则包含不可见零宽 Unicode 字符
- `anomaly/rules.py:253` — 空 dict 触发不必要的 `_STATICAL_COLUMNS` 回退
- `anomaly/report.py:56` — 未清洗的 `data_type` 用于输出文件名，允许路径注入

---

## 五、按模块分析

### 5.1 func/ 处理引擎

**状态**: 核心逻辑正确，但代码组织需要改进

**优点**:
- 各处理器独立运行，互不耦合
- `orchestration.py` 提供统一调度入口
- 异常值检测模块设计合理（规则→检测→过滤→报告）
- 台账系统支持模糊匹配

**问题**:
- 8 个文件超过 800 行限制
- 10 个函数超过 100 行
- 广泛的就地修改（mutation）违反项目编码规范
- 配置缓存存在竞态条件和污染风险
- `excel_worktime.py` 和 `excel_worktime_multifile.py` 后处理管道重复

### 5.2 gui/ Flet GUI

**状态**: 功能完整，但代码组织和 i18n 有问题

**优点**:
- 清晰的三段式拆分（main → components → logic）
- 日志系统支持 CLI/GUI 共享
- 组件按功能拆分

**问题**:
- `logic.py` 1442 行，应拆分
- `_MODULE_LABELS` 在导入时冻结翻译
- 语言切换对话框泄漏
- 12+ 处 FilePicker 创建模式重复
- 线程安全问题（共享状态无锁）

### 5.3 tauri_bridge.py

**状态**: 功能完整，但体积过大且缺少验证

**优点**:
- JSON-RPC 协议实现完整
- SSRF 防护、路径遍历检查
- 错误消息剥离 traceback

**问题**:
- 1619 行，应拆分为包
- 18 个台账 CRUD 方法重复，应使用工厂模式
- 9 个 RPC 方法缺少必需参数验证
- 无优雅关闭、无任务超时
- 错误响应格式不一致

### 5.4 src/ Tauri 前端

**状态**: UI 功能丰富，但性能和测试需要改进

**优点**:
- 共享组件库（ui-components.tsx、icons.tsx）
- i18n 架构合理（namespace、fallback）
- ErrorBoundary 组件存在

**问题**:
- 所有页面同时挂载（display:none 模式）
- 68% 组件无测试
- 大量 unsafe 类型断言
- 30 个 useState 在 DataSyncPage
- 图标重复（Sidebar、Toast 各自定义）
- 多处硬编码中文字符串

### 5.5 测试覆盖

| 层 | 模块数 | 有测试 | 覆盖率 |
|----|--------|--------|--------|
| func/ | 42 | 29 | 69% |
| gui/ | 28 | 23 | 82% |
| src/ | 44 | 14 | 32% |
| **总计** | **114** | **66** | **58%** |

**关键缺失**:
- `func/building.py`、`func/excel_fuel_wide.py`、`func/sync/db_client.py` — 核心模块零覆盖
- Tauri 30 个组件无测试
- 5 个测试无断言

### 5.6 安全性

**优点**:
- SQL 查询使用参数化
- SSRF 防护阻止回环/链路本地/云元数据地址
- 路径遍历检查拒绝 `..` 组件
- SSL 验证启用（certifi 回退）
- `config.user.json` 已 gitignore
- 加密存储使用 PBKDF2（480k 迭代）+ Fernet
- 基于 Machine-ID 的密钥派生

**需加固**:
- 硬编码回退密码短语
- 配置文件无限制权限
- `write_text_file` 无路径白名单
- DNS 重绑定攻击
- LLM/API 客户端未强制 HTTPS

### 5.7 国际化

**架构**: Flet 和 Tauri 的 i18n 实现架构合理（namespace、fallback 链、语言规范化）

**严重问题**:
- ~360 个翻译是机器生成的伪翻译（"filefile"、"item"、"columnfilter"）
- 蒙文翻译仅 ~30% 是真正的蒙文
- 多处硬编码中文字符串（领域特定列名、默认值）
- 英文翻译中残留全角中文标点

---

## 六、优化方案

### 6.1 短期（1-2 周）— 修复关键问题

| # | 任务 | 优先级 | 预估工时 | 涉及文件 |
|---|------|--------|---------|---------|
| 1 | 修复 `config_loader.load_config()` 返回深拷贝 | CRITICAL | 2h | config_loader.py |
| 2 | 修复 `_deep_merge` 使用 `copy.deepcopy` | CRITICAL | 1h | config_loader.py |
| 3 | 修复 `gui/logic.py:769` NameError | CRITICAL | 1h | gui/logic.py |
| 4 | 修复 `ledger_match.py:196` 挖掘机匹配 | CRITICAL | 1h | ledger_match.py |
| 5 | 修复 `db_client.py:48` LIKE 通配符转义 | CRITICAL | 1h | sync/db_client.py |
| 6 | 修复 `sync_engines.py:515` 全部回滚 → savepoint | CRITICAL | 4h | sync/sync_engines.py |
| 7 | 为 `tauri_bridge.py` 9 个 RPC 方法添加参数验证 | HIGH | 4h | tauri_bridge.py |
| 8 | 修复 `update_device_load_map` 竞态条件 | HIGH | 2h | config_loader.py |
| 9 | 修复 `gui/main.py:66` 语言切换对话框泄漏 | HIGH | 1h | gui/main.py |
| 10 | 修复 `_MODULE_LABELS` 导入时冻结翻译 | HIGH | 2h | gui/logic.py |
| **合计** | | | **~19h** | |

### 6.2 中期（1 个月）— 代码组织与测试

| # | 任务 | 优先级 | 预估工时 | 涉及文件 |
|---|------|--------|---------|---------|
| 1 | 拆分 `tauri_bridge.py` 为包（protocol + methods/） | HIGH | 8h | tauri_bridge.py |
| 2 | 拆分 `gui/logic.py` 为多个模块 | HIGH | 6h | gui/logic.py |
| 3 | 提取 `useConfigSection` hook 消除 7x 重复 | HIGH | 4h | src/components/user-config/ |
| 4 | 提取台账 RPC 工厂消除 18 个重复方法 | HIGH | 4h | tauri_bridge.py |
| 5 | 提取 FilePicker 创建模式为共享函数 | MEDIUM | 3h | gui/components/ |
| 6 | 提取工时后处理管道为共享函数 | MEDIUM | 2h | excel_worktime*.py |
| 7 | 为 `func/building.py`、`excel_fuel_wide.py`、`sync/db_client.py` 添加测试 | HIGH | 6h | tests/ |
| 8 | 为 Tauri 关键页面添加测试 | HIGH | 8h | src/test/ |
| 9 | 修复 App.tsx 使用条件渲染替代 display:none | HIGH | 4h | src/App.tsx |
| 10 | 添加 React Error Boundary 包裹页面 | HIGH | 2h | src/App.tsx |
| 11 | 修复 `db_client.py` 添加上下文管理器和 connect_timeout | HIGH | 2h | sync/db_client.py |
| 12 | 为 `api_client.py` 添加重试逻辑 | HIGH | 3h | sync/api_client.py |
| 13 | 设置 `config.user.json` 文件权限为 0600 | MEDIUM | 1h | config_loader.py |
| 14 | 修复 `write_text_file` 添加路径白名单 | MEDIUM | 2h | tauri_bridge.py |
| **合计** | | | **~55h** | |

### 6.3 长期（季度）— 架构改进

| # | 任务 | 优先级 | 预估工时 | 涉及文件 |
|---|------|--------|---------|---------|
| 1 | 拆分 `config_loader.py` 为 5 个领域模块 | CRITICAL | 8h | func/config_*.py |
| 2 | 拆分 `label_maintenance_with_llm.py` 为 4 个模块 | CRITICAL | 12h | func/llm_*.py |
| 3 | 拆分 `daily_report.py` 长函数 | HIGH | 6h | func/daily_report.py |
| 4 | 拆分 `excel_tire.py` 长函数 | HIGH | 6h | func/excel_tire.py |
| 5 | 拆分 `excel_production_enhanced.py` 长函数 | HIGH | 6h | func/excel_production_enhanced.py |
| 6 | 拆分 Tauri 大页面为子组件 | HIGH | 12h | src/components/pages/ |
| 7 | 重新翻译所有 locale 文件（en + mn） | HIGH | 16h | gui/locales/ + src/locales/ |
| 8 | 修复所有 mutation 模式为不可变模式 | MEDIUM | 12h | 多文件 |
| 9 | 将 `scikit-learn` 和 `psycopg2` 改为可选依赖 | MEDIUM | 4h | pyproject.toml |
| 10 | 为 `sync_engines.py` 添加批量 INSERT | MEDIUM | 4h | sync/sync_engines.py |
| 11 | 优化 `ledger_base.py` 使用向量化替代 iterrows | MEDIUM | 3h | func/ledger_base.py |
| 12 | 为 Tauri 剩余组件添加测试（目标 80%） | MEDIUM | 20h | src/test/ |
| 13 | 添加无障碍改进（aria-label、焦点陷阱、对比度） | LOW | 8h | src/components/ |
| 14 | 统一 Tauri 错误响应格式 | LOW | 3h | tauri_bridge.py |
| 15 | 添加优雅关闭和任务超时 | LOW | 4h | tauri_bridge.py |
| **合计** | | | **~124h** | |

---

## 七、技术债务清单（按优先级排序）

| # | 债务 | 严重度 | 影响范围 | 修复成本 |
|---|------|--------|---------|---------|
| 1 | 配置缓存竞态 + 污染 | CRITICAL | 所有配置读写 | 低 |
| 2 | 超大文件（5 个 >1000 行） | CRITICAL | 开发效率 | 高 |
| 3 | 翻译质量（~360 个伪翻译） | HIGH | 用户体验 | 中 |
| 4 | Tauri 测试缺口（68% 无覆盖） | HIGH | 回归风险 | 高 |
| 5 | Tauri Bridge 输入验证缺失 | HIGH | 运行时错误 | 低 |
| 6 | 配置文件竞态条件 | HIGH | 数据一致性 | 低 |
| 7 | 就地修改（mutation）模式 | MEDIUM | 并发安全 | 中 |
| 8 | 代码重复（台账 CRUD、FilePicker、config section） | MEDIUM | 维护成本 | 中 |
| 9 | 安全加固（HTTPS 强制、路径白名单） | MEDIUM | 安全风险 | 低 |
| 10 | 性能（N+1 查询、逐行 INSERT） | MEDIUM | 同步速度 | 中 |
| 11 | 魔法数字 | LOW | 可维护性 | 低 |
| 12 | 无障碍改进 | LOW | 可访问性 | 中 |

---

## 八、附录

### A. 审计方法论

1. **并行扫描**: 15 个审计 agent 并行运行，每个专注特定维度
2. **维度覆盖**: 代码质量、架构设计、安全性、性能、测试覆盖、国际化/无障碍
3. **严重度分级**: CRITICAL（数据丢失/崩溃）→ HIGH（功能缺陷）→ MEDIUM（维护性）→ LOW（建议）
4. **验证**: 每个发现包含具体文件路径、行号、失败场景和修复建议

### B. 文件统计

| 类别 | 文件数 | 总行数 |
|------|--------|--------|
| func/ Python | 54 | ~18,000 |
| gui/ Python | 34 | ~10,000 |
| tauri_bridge.py | 1 | 1,619 |
| src/ TypeScript | 55 | ~12,000 |
| tests/ Python | 53 | ~15,000 |
| src/test/ TypeScript | 15 | ~3,000 |
| **总计** | **212** | **~60,000** |

### C. 积极发现

审计也发现了以下值得保持的良好实践：

- SQL 查询全面使用参数化，无注入风险
- SSRF 防护阻止回环/链路本地/云元数据地址
- 加密存储使用 PBKDF2（480k 迭代）+ Fernet + Machine-ID
- 错误消息剥离 traceback，防止信息泄露
- `config.user.json` 已 gitignore
- SSL 验证启用并有 certifi 回退
- Flet 和 Tauri 的 i18n 架构设计合理
- 测试覆盖 1,355 个用例，核心模块覆盖较好
- `orchestration.py` 提供清晰的统一调度入口
- 异常值检测模块设计合理，支持多种检测方法

---

*报告生成时间: 2026-08-24*
*审计工具: Claude Code Workflow (15 parallel agents)*
