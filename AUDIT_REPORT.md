# MiningProcessor 全面审计报告

## 执行摘要 (Executive Summary)

本次审计覆盖了 MiningProcessor 项目的架构、代码质量、安全性和性能四个维度。项目整体结构合理，GUI 与 func/ 的依赖方向正确，配置系统设计良好，SQL 注入防护到位。然而，存在 **1 个严重安全漏洞**（硬编码加密密钥导致凭证加密形同虚设）、**9 个高优先级问题**（包括线程安全隐患、DataFrame 原地修改、核心处理引擎零测试等），以及大量中低优先级的技术债务。

**整体评估：MIXED** — 基础架构稳固，但核心业务逻辑层（Excel 处理引擎）缺乏测试保护且存在性能瓶颈，安全存储存在根本性缺陷需要立即修复。

---

## 发现统计 (Findings Statistics)

| 严重程度 | 数量 | 占比 |
|----------|------|------|
| CRITICAL | 1    | 1.4% |
| HIGH     | 12   | 17.1% |
| MEDIUM   | 30   | 42.9% |
| LOW      | 27   | 38.6% |
| **合计** | **70** | 100% |

> 注：跨维度重复发现已合并去重（如 "traceback 丢失" 同时出现在架构和代码质量中、"shift 检测重复" 同时出现在架构和性能中等）。

---

## 关键发现 (Critical Findings)

### CR-01: 加密密钥硬编码在源码中，凭证加密形同虚设

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/secret_store.py` 第 33-34 行
- **CWE**: CWE-321 (Use of Hard-coded Cryptographic Key)
- **说明**: `_PASSPHRASE` 和 `_SALT` 是静态字节串，嵌入在提交到仓库的源码中。PBKDF2 派生过程本身安全（480,000 次迭代，SHA256），但密钥材料完全可从源码恢复。任何能同时访问源码和 `config.user.json` 的攻击者均可解密所有存储的数据库和 API 密码。
- **影响**: 所有 `__enc__` 前缀的加密凭证对本地攻击者完全透明。
- **建议**: 迁移到 OS 级密钥链集成（macOS Keychain / Linux Secret Service），或使用运行时用户输入的密码派生密钥，或使用权限受限的机器专属密钥文件（0600 权限，仓库外存放）。

---

## 高优先级发现 (High Priority Findings)

### HIGH-01: config_loader 线程安全竞态条件

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/config_loader.py` 第 203-224 行
- **类别**: 架构 / 并发
- **说明**: `_config_cache` 和 `_config_cache_mtime` 在 `load_config()` 和 `_invalidate_config_cache()` 中的读写未受锁保护。GUI 后台线程处理数据时会并发调用 `load_config()`，存在 TOCTOU 竞态，可能导致返回过时配置。
- **建议**: 扩展 `_runtime_lock` 以保护缓存读写，或使用独立的 `_cache_lock`。

### HIGH-02: match_sheets 原地修改 DataFrame，违反不可变性标准

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/ledger_postprocess.py` 第 116 行
- **类别**: 架构 / 不可变性
- **说明**: `match_sheets` 遍历 sheets 并直接向 DataFrame 追加列。当 `excel_batch.py` 将 DataFrame 存入 `all_results` 后传入 `match_sheets`，原地修改会污染缓存结果。
- **建议**: 在每次 sheet 迭代开始时 `df = df.copy()`，返回新 DataFrame 而非修改原始对象。

### HIGH-03: _execute_task 错误处理丢失完整 traceback

- **文件**: `/Users/kearney/CODE/MiningProcessor/gui/logic.py` 第 150-194 行
- **类别**: 架构 / 代码质量（跨维度重复，已合并）
- **说明**: `except Exception as ex` 仅保留 `str(ex)`，原始 traceback 完全丢失。生产环境调试极为困难。
- **建议**: 在 except 块中使用 `logger.exception('Processing failed', exc_info=True)` 记录完整 traceback。

### HIGH-04: Tauri Bridge 路径遍历漏洞

- **文件**: `/Users/kearney/CODE/MiningProcessor/tauri_bridge.py` 第 681、572、578、585、597、700、704、806 行
- **CWE**: CWE-22 (Path Traversal)
- **类别**: 安全
- **说明**: 多个 RPC 方法接受未消毒的文件/目录路径，可被用于探测任意目录存在性或读取 Excel 兼容文件。
- **建议**: 对所有路径参数添加消毒逻辑：解析为绝对路径、验证在允许目录内、拒绝含 `..` 的路径段。

### HIGH-05: 完整异常信息泄露到前端和 UI

- **文件**: `/Users/kearney/CODE/MiningProcessor/tauri_bridge.py` 第 860 行；`gui/logic.py` 第 558、737 行
- **CWE**: CWE-209 (Information Exposure Through Error Messages)
- **类别**: 安全
- **说明**: Python 异常消息（含主机名、端口、用户名、文件路径等）直接发送到 Tauri 前端和 GUI 界面。
- **建议**: 服务端记录完整 traceback，仅向客户端发送通用错误标识（如 `"Internal error (ref: ERR-XXXX)"`）。

### HIGH-06: 核心 Excel 处理引擎零单元测试

- **文件**: `func/excel_fuel.py`（225 行）、`func/excel_electrical.py`（163 行）、`func/excel_production_enhanced.py`（517 行）
- **类别**: 测试
- **说明**: 三个核心处理引擎共 905 行代码，零单元测试。所有引用均使用 mock，实际的 Excel 解析逻辑（列检测、数据提取、输出格式化）完全未被测试覆盖。
- **建议**: 创建小型测试 Excel fixture，编写验证列检测、数据转换、输出结构的单元测试。

### HIGH-07: func/sync/ 子包（1593 行）零单元测试

- **文件**: `func/sync/`（6 个模块）
- **类别**: 测试
- **说明**: 包括 file_processors.py（469 行）、sync_engines.py（222 行）、core.py（322 行）、row_helpers.py（274 行）均无测试。
- **建议**: 为 file_processors、sync_engines、row_helpers 分别添加单元测试，使用 mock 的 HTTP/DB 客户端和真实 Excel fixture。

### HIGH-08: iterrows + 嵌套列循环导致严重性能瓶颈

- **文件**: `func/excel_production_enhanced.py` 第 222 行；`func/excel_fuel.py` 第 106 行
- **类别**: 性能
- **说明**: 两个核心处理器均在 Python 层面执行 O(rows × columns) 的双重循环。对于典型的采矿生产表（数百行 × 数十列），性能极差。
- **建议**: 在行循环前预分类列，使用向量化 pandas 操作（melt/stack）提取数据，消除双层 Python 循环。

### HIGH-09: 行级逐条 ledger 匹配应改为批量匹配

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/ledger_postprocess.py` 第 53 行
- **类别**: 性能
- **说明**: 每行独立触发模糊匹配。采矿数据中设备名称大量重复，批量匹配（先提取唯一名称，匹配一次，再映射回）可减少调用次数 10-50 倍。
- **建议**: 提取唯一设备名称 → 批量匹配 → 使用 `.map()` 映射回 DataFrame。

### HIGH-10: clean_string 逐单元格调用开销过大

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/string_utils.py` 第 15 行
- **类别**: 性能
- **说明**: 每个单元格值调用 clean_string，执行 pd.isna()、str()、strip()、三次 .replace() 和 re.sub()。正则未预编译，无数值快速路径。
- **建议**: 模块级预编译正则 `_MULTI_SPACE = re.compile(r' {2,}')`；添加数值类型快速路径跳过完整处理。

### HIGH-11: 生产表全文扫描定位表头

- **文件**: `/Users/kearney/CODE/MiningProcessor/func/excel_production_enhanced.py` 第 161 行
- **类别**: 性能
- **说明**: `df_raw.apply(lambda row: row.astype(str).str.contains(...).any(), axis=1)` 将整个 DataFrame 所有单元格转为字符串搜索目标文本，而表头预期在前 ~20 行。
- **建议**: 限制搜索范围至 `df_raw.iloc[:20]`，或仅搜索第一列。

### HIGH-12: Shift 检测逻辑跨 4+ 模块重复且行为不一致

- **文件**: `func/excel_fuel.py` 第 46-53 行、`func/excel_electrical.py` 第 53-64 行、`func/excel_production_enhanced.py`、`func/excel_utils.py`
- **类别**: 架构 / 重复
- **说明**: 白班/夜班检测在 4 处独立实现，分别处理中文、蒙古文、英文大小写，逻辑不一致。
- **建议**: 合并到 `excel_utils.py resolve_shift()` 的单一共享函数中，处理所有已知模式。

---

## 中等优先级发现 (Medium Priority Findings)

### 架构类（MEDIUM）

| ID | 标题 | 文件 | 说明 |
|----|------|------|------|
| M-01 | GUI 组件直接导入 config_loader 内部 | `gui/components/common.py` | 模块导入时调用 `get_user_config`，产生隐式副作用 |
| M-02 | gui/logic.py 是单体调度中心（12 个 func/ 导入） | `gui/logic.py` | `_execute_task` 是不断增长的 if/elif 链，违反开闭原则 |
| M-03 | config_loader.py 是 God Module（580 行混合职责） | `func/config_loader.py` | 配置管理、MineBase 配置、台账缓存 I/O 混在同一文件 |
| M-04 | process_diesel_data 返回 None 无调用方验证 | `func/excel_fuel.py` 第 18-20、185 行 | 失败时返回 None，调用方假设成功继续执行 |
| M-05 | user_config.py 组件包含业务逻辑（900 行） | `gui/components/user_config.py` | 配置验证、关键字管理、列映射操作应移至 func/ |
| M-06 | _strip_date_only_times 跨模块重复 | `func/ledger_postprocess.py`、`gui/components/common.py` | 近乎相同的函数在两处实现 |
| M-07 | 批量处理静默吞没模块级错误 | `func/excel_batch.py` 第 147-194 行 | 错误仅记录日志，不传回调用方，无法区分"无文件"和"全部失败" |

### 代码质量类（MEDIUM）

| ID | 标题 | 文件 | 说明 |
|----|------|------|------|
| M-08 | on_batch_process 169 行 | `gui/logic.py` 第 396-565 行 | 文件扫描、确认对话框、进度条、取消事件混在一个函数 |
| M-09 | process_files 135 行 | `func/excel_batch.py` 第 102-236 行 | 四种模块类型处理、日期过滤、台账匹配、输出写入全在一个函数 |
| M-10 | _table_merge_and_write 128 行 | `func/excel_batch.py` 第 499 行 | 班次默认值、生产聚合、燃料聚合、合并队列构建、输出写入全在一个函数 |
| M-11 | on_sync_process 110 行 | `gui/logic.py` 第 634-743 行 | 参数收集、验证、线程执行、结果展示混在一起 |
| M-12 | gui/logic.py 超过 800 行限制（849 行） | `gui/logic.py` | 应拆分为 logic_processing.py、logic_batch.py、logic_sync.py |
| M-13 | _execute_task 嵌套深度 6 层 | `gui/logic.py` 第 158-164 行 | try → if production → if isdir → else 嵌套过深 |
| M-14 | wire_processing_buttons 62 行含 5 个重复闭包 | `gui/logic.py` 第 570 行 | 应提取工厂函数生成处理器闭包 |
| M-15 | _active_snackbar 可变全局状态 | `gui/logic.py` 第 42 行 | 异步清理闭包与显示函数之间的竞态窗口 |
| M-16 | SortState.apply_to_dataframe 静默吞没异常 | `gui/components/common.py` 第 253-256 行 | 排序失败时静默返回未排序 DataFrame |
| M-17 | 全面缺失类型注解（gui/logic.py 48/55 函数） | `gui/logic.py` | 公共回调函数缺少参数和返回类型注解 |
| M-18 | EquipmentLedger 类缺少 docstring | `func/equipment_ledger.py` 第 25 行 | 关键公共类无文档说明 |
| M-19 | _aggregate_production_data 84 行 | `func/excel_batch.py` 第 298 行 | 卡车/挖掘机聚合是近乎相同的代码块 |

### 安全类（MEDIUM）

| ID | 标题 | 文件 | 说明 |
|----|------|------|------|
| M-20 | .serena/ 目录未被 .gitignore 排除 | `.gitignore` | `git add .` 可能意外提交 agent 工具元数据 |
| M-21 | psycopg2-binary 用于生产环境且无版本上限 | `pyproject.toml` 第 16 行 | 官方文档建议生产使用源码分发版；无版本上限有破坏性变更风险 |

### 性能类（MEDIUM）

| ID | 标题 | 文件 | 说明 |
|----|------|------|------|
| M-22 | 批量模式下模块串行处理 | `func/excel_batch.py` 第 147 行 | 四个独立模块类型串行执行，并行可提速 ~4x |
| M-23 | 冗余 Excel 文件重读用于台账匹配 | `func/ledger_postprocess.py` 第 169 行 | 刚写入的文件立即重新读取，应传递 preloaded_sheets |
| M-24 | 电气处理器逐单元格提取 | `func/excel_electrical.py` 第 83 行 | O(rows × date_columns) 嵌套循环应向量化 |
| M-25 | process_sheet2 手动 iloc 迭代 | `func/excel_production_enhanced.py` 第 310 行 | 应使用向量化操作替代逐行 iloc 访问 |

### 测试类（MEDIUM）

| ID | 标题 | 文件 | 说明 |
|----|------|------|------|
| M-26 | test_ledger_match_improvements.py 测试琐碎数据结构 | `tests/test_ledger_match_improvements.py` | 验证 Python 内置切片行为而非生产代码 |
| M-27 | test_tab_switching.py 测试本地重实现 | `tests/test_tab_switching.py` | 从未导入实际的 _select_tab 函数 |
| M-28 | test_drag_resize.py 使用源码检查而非行为测试 | `tests/test_drag_resize.py` | inspect.getsource() 断言字符串，重构即失效 |
| M-29 | 无畸形输入文件或 I/O 错误的边界测试 | `tests/` | 缺少损坏 Excel、权限错误、并发访问等场景 |
| M-30 | 多个测试文件重复 fixture 模式 | `tests/` | 应提取到 conftest.py 的共享 fixture |

---

## 低优先级发现 (Low Priority Findings)

### 架构 / 命名

| ID | 标题 | 文件 |
|----|------|------|
| L-01 | 处理器函数命名不一致 | `func/excel_fuel.py` 等 |
| L-02 | logic.py 从 components/common.py 导入 _log_message | `gui/logic.py` 第 23 行 |

### 代码质量

| ID | 标题 | 文件 |
|----|------|------|
| L-03 | _execute_task 51 行（边界值） | `gui/logic.py` 第 144 行 |
| L-04 | Excel sheet 名称长度限制 31 为魔术数字 | `func/excel_batch.py` 第 655 行 |
| L-05 | 进度分数 1/3, 2/3 为字面量 | `func/excel_batch.py` 第 511 行 |
| L-06 | 默认年份 2025 硬编码 | `gui/logic.py` 第 131 行 |
| L-07 | `del btn` 代码异味 | `gui/logic.py` 第 199 行 |
| L-08 | base_keys_ok / right_keys_ok 计算但未使用 | `func/excel_batch.py` 第 598-599 行 |
| L-09 | 35 处 f-string 日志调用阻止惰性求值 | `func/excel_batch.py` |
| L-10 | _show_snackbar 中 3 个重复 try/except | `gui/logic.py` 第 46 行 |
| L-11 | _batch_target 使用可变 dict 传播异常 | `gui/logic.py` 第 533-545 行 |
| L-12 | f-string 用于 logging.info 调用 | `gui/logic.py` 第 158 行 |
| L-13 | OilLedger 类缺少 docstring | `func/oil_ledger.py` 第 17 行 |
| L-14 | has_*_ledger_cache 函数缺少 docstring | `func/config_loader.py` 第 454、483 行 |
| L-15 | _last_directory 全局可变列表 | `gui/components/common.py` 第 15 行 |
| L-16 | create_column_mapping_dialog 78 行 | `gui/components/common.py` 第 405 行 |
| L-17 | common.py 类型注解缺失 | `gui/components/common.py` |
| L-18 | excel_batch.py 内部函数类型注解缺失 | `func/excel_batch.py` 第 26 行 |
| L-19 | 聚合前不必要的 DataFrame copy | `func/excel_batch.py` 第 319 行 |

### 安全

| ID | 标题 | 文件 |
|----|------|------|
| L-20 | config.user.json 权限过宽（644） | `config.user.json` |
| L-21 | 文件路径处理前无输入验证 | `func/excel_batch.py` 第 57 行 |

### 性能

| ID | 标题 | 文件 |
|----|------|------|
| L-22 | parse_filename 中内联正则编译 | `func/excel_production_enhanced.py` 第 54 行 |
| L-23 | 电气处理器循环内正则编译 | `func/excel_electrical.py` 第 89 行 |
| L-24 | config accessor 函数重复调用 load_config | `func/config_loader.py` 第 282 行 |
| L-25 | strip_date_column 使用 apply 替换年份 | `func/excel_utils.py` 第 108 行 |
| L-26 | 日期过滤中冗余 to_datetime 转换 | `func/excel_batch.py` 第 255 行 |
| L-27 | GUI 逻辑层热切导入重型依赖 | `gui/logic.py` 第 11 行 |

### 测试

| ID | 标题 | 文件 |
|----|------|------|
| L-28 | test_log_consumer.py 使用真实 time.sleep | `tests/test_log_consumer.py` |
| L-29 | test_logic_helpers.py 使用真实文件 I/O | `tests/test_logic_helpers.py` |
| L-30 | 模块级 importlib 加载是隐式副作用 | `tests/test_gui_components.py` |
| L-31 | 测试命名语言不一致（英文函数名、中文 docstring） | `tests/` |

---

## 行动计划 (Action Plan)

### Phase 1 — 立即修复 (1-2 天)

**目标**: 消除安全漏洞和数据完整性风险

| 编号 | 发现 | 修复内容 | 预估工时 |
|------|------|----------|----------|
| 1 | CR-01 | 迁移 secret_store.py 到 OS 密钥链或用户密码派生 | 4-8h |
| 2 | HIGH-02 | ledger_postprocess.py: sheet 迭代前 copy DataFrame | 1h |
| 3 | HIGH-03 | gui/logic.py _execute_task: 添加 logger.exception() | 30min |
| 4 | M-20 | .gitignore 添加 .serena/ | 5min |
| 5 | L-20 | config_loader.py _save_json: 写入后 os.chmod(0o600) | 15min |

### Phase 2 — 短期改进 (1-2 周)

**目标**: 修复安全边界、建立测试基础、解决线程安全

| 编号 | 发现 | 修复内容 | 预估工时 |
|------|------|----------|----------|
| 6 | HIGH-04 | Tauri Bridge: 添加路径消毒和目录白名单 | 4-6h |
| 7 | HIGH-05 | Tauri Bridge + logic.py: 异常消息脱敏 | 2-3h |
| 8 | HIGH-01 | config_loader: 扩展锁保护缓存读写 | 2-3h |
| 9 | HIGH-06 | 为三个核心处理器创建 Excel fixture 和单元测试 | 8-12h |
| 10 | HIGH-07 | 为 func/sync/ 添加单元测试框架 | 8-12h |
| 11 | L-09 | excel_batch.py: f-string 日志 → %-formatting | 1h |
| 12 | M-06 | 提取 _strip_date_only_times 到 excel_utils.py | 30min |

### Phase 3 — 中期优化 (2-4 周)

**目标**: 性能优化、结构重构、提升代码质量

| 编号 | 发现 | 修复内容 | 预估工时 |
|------|------|----------|----------|
| 13 | HIGH-08 | 向量化 process_sheet1 和 process_diesel_data 的行列循环 | 8-12h |
| 14 | HIGH-09 | ledger_postprocess: 批量匹配（唯一名称 → 映射回） | 4-6h |
| 15 | HIGH-10 | string_utils: 预编译正则 + 数值快速路径 | 2-3h |
| 16 | HIGH-11 | 限制目标文本扫描范围至前 20 行 | 1h |
| 17 | HIGH-12 | 合并 shift 检测到 excel_utils.resolve_shift() | 2-3h |
| 18 | M-12 | 拆分 gui/logic.py 为 3 个文件 | 4-6h |
| 19 | M-08, M-09, M-10 | 拆分大函数（on_batch_process, process_files, _table_merge_and_write） | 6-8h |
| 20 | M-02 | _execute_task: 引入处理器注册表模式 | 3-4h |
| 21 | M-03 | 拆分 config_loader.py 为 3 个聚焦模块 | 4-6h |
| 22 | M-22 | 批量处理并行化（ThreadPoolExecutor） | 4-6h |
| 23 | M-23 | 消除台账匹配的冗余文件重读 | 2-3h |

### Phase 4 — 长期改进 (持续进行)

**目标**: 完善测试覆盖、统一命名、消除技术债务

| 编号 | 发现 | 修复内容 | 预估工时 |
|------|------|----------|----------|
| 24 | M-17, L-17, L-18 | 添加类型注解 | 持续，每次 PR 改动时补充 |
| 25 | M-26~M-30 | 改写低质量测试、添加边界测试、统一 fixture | 8-12h |
| 26 | M-05 | user_config.py 业务逻辑提取到 func/ | 4-6h |
| 27 | L-01 | 统一处理器函数命名 | 2h |
| 28 | L-04~L-06 | 消除魔术数字 | 1h |
| 29 | L-09 | 全面日志格式化审计 | 2h |
| 30 | M-21 | psycopg2-binary → psycopg2 + 版本上限 | 2h |

---

## 快速收益 (Quick Wins)

以下修复投入少（<1 小时）但影响显著：

1. **.gitignore 添加 .serena/** — 5 分钟，防止意外提交 agent 元数据
2. **_execute_task 添加 logger.exception()** — 30 分钟，立即改善生产环境调试能力
3. **match_sheets 添加 df.copy()** — 1 小时，消除数据污染风险
4. **config.user.json 写入后 chmod 0600** — 15 分钟，收紧文件权限
5. **_strip_date_only_times 提取到 excel_utils** — 30 分钟，消除跨模块重复
6. **excel_batch.py f-string → %-formatting** — 1 小时，35 处日志调用获得惰性求值
7. **限制目标文本扫描范围至前 20 行** — 1 小时，消除不必要的全文扫描
8. **string_utils 预编译正则** — 30 分钟，消除逐次编译开销

---

## 系统性问题 (Systemic Issues)

以下模式反映了更深层的架构问题，需要在团队层面关注：

### 1. 核心业务逻辑缺乏测试保护

三个核心 Excel 处理引擎（共 905 行）和 sync 子包（共 1593 行）合计 2498 行业务关键代码完全无单元测试。所有测试引用均使用 mock，这意味着实际的数据解析逻辑可以被任意修改而不会触发任何测试失败。这是最严重的系统性风险——业务逻辑的正确性没有自动化保障。

### 2. 处理器脚本的结构重复未被抽象

6 个 Excel 处理器独立实现相同的处理流程（打开 Excel → 过滤 sheet → 解析表头 → 提取数据 → 去重 → 导出）。shift 检测在 4 处独立实现且行为不一致。这表明项目缺少一个共享的处理器基类或处理管道，导致每个新处理器都需要重新实现基础设施代码，且修复一个处理器的 bug 不会自动修复其他处理器的同类问题。

### 3. GUI 层职责渗透

gui/logic.py 作为调度中心直接导入 12 个 func/ 模块，gui/components/user_config.py（900 行）包含大量业务逻辑。GUI 层本应是薄编排层，但实际上已经承担了数据验证、关键字管理、列映射等业务职责。这种职责渗透使得 func/ 层难以独立测试和复用。

### 4. 错误处理策略不一致

项目中存在至少 4 种不同的错误处理模式：(a) 返回 None（excel_fuel.py）、(b) 捕获并记录后继续（excel_batch.py）、(c) 捕获并转换为字符串（gui/logic.py）、(d) 静默吞没（gui/components/common.py SortState）。缺乏统一的错误处理策略，导致错误信息在传递过程中不断丢失，最终用户看到的往往是无意义的字符串而非可操作的诊断信息。

### 5. 性能反模式的系统性存在

iterrows + 嵌套列循环、逐单元格 clean_string 调用、逐行模糊匹配——这些性能反模式不是个别现象，而是贯穿所有处理器的系统性模式。它们共同表明项目在数据处理时采用了"逐行逐列"的编程范式，而非 pandas 设计初衷的"向量化批量操作"范式。将处理器重构为向量化操作应作为中期技术投资的重点。

### 6. 全局可变状态的蔓延

`_btn_original_styles`、`_active_snackbar`、`_last_directory`、`_runtime_config`、`_config_cache` 等模块级可变状态散布在 gui/logic.py、gui/components/common.py 和 func/config_loader.py 中。这些状态使代码非可重入、难以测试（测试间状态泄漏）、且在并发场景下存在竞态条件。应逐步迁移到实例属性或通过参数传递。

---

## 知识图谱分析

### 核心枢纽节点（高连接度）
| 节点 | 连接数 | 含义 |
|------|--------|------|
| tauri_bridge.py | 87 | Python↔Tauri 桥接层，所有 RPC 方法的入口 |
| config_loader.py | 60 | 全局配置中心，被所有模块依赖 |
| clean_string() | 60 | 字符串清洗工具，被 8+ 模块调用 |
| logic.py | 52 | GUI 逻辑层，处理器调度中心 |
| EquipmentLedger | 47 | 设备台账，跨多个社区的桥接节点 |

### 跨社区桥接节点（高介数中心性）
| 节点 | 介数中心性 | 连接的社区 |
|------|-----------|-----------|
| config_loader.py | 0.264 | 几乎所有社区 |
| sync/core.py | 0.214 | 同步引擎 ↔ GUI |
| usePythonBridge.ts | 0.212 | Tauri前端 ↔ Python后端 |
| logic.py | 0.124 | GUI组件 ↔ 处理器 |
| tauri_bridge.py | 0.118 | Tauri ↔ Python |

### 图谱统计
- 15 个连通分量（主分量 1723 节点，14 个小分量为配置文件、构建脚本等）
- 图密度: 0.0019（稀疏，模块间耦合集中于少数枢纽）
- 平均聚类系数: 0.1483（社区内部连接适中）
- Token 压缩比: 22.2x（图谱查询比全量阅读节省 22 倍 token）

---

*审计方法: 5 维度并行 Agent 审计（架构/代码质量/安全/性能/测试）+ 知识图谱结构分析*
*审计代理: 6 个，总 token 消耗 443k，运行时间约 23 分钟*
*知识图谱: 1,888 节点 / 3,426 边 / 104 社区*
*完整图谱位于: graphify-out/ (Obsidian vault, HTML 可视化, JSON)*

