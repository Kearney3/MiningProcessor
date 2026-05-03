# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

这是一个矿山运营 Excel 报表处理项目，包含两类入口：

- **CLI 脚本**：直接处理单个 Excel 文件或整批文件夹，结果写回输入目录。
- **Flet GUI**：把常用处理流程、配置编辑、日志展示整合到桌面界面中。

核心依赖是 `pandas + openpyxl` 负责 Excel 解析与导出，`flet` 负责 GUI，`rapidfuzz` 预留给设备名称模糊匹配。

## 常用命令

### 环境与依赖

```bash
# Python 版本以仓库 .python-version 为准
uv sync
```

### 运行 GUI

```bash
python gui/main.py
python -m gui
python -m flet gui/main.py
```

`pyproject.toml` 里还注册了入口脚本：

```bash
uv run main.py
```

### 运行各处理脚本

这些脚本都位于 `func/` 下，通常直接这样运行：

```bash
python func/excel_fuel.py <输入文件> [--year 年份]
python func/excel_electrical.py <输入文件> [--year 年份]
python func/excel_worktime.py <输入文件或文件夹> [--year 年份] [--month 月份]
python func/excel_production.py <输入文件夹路径> [--version 版本]
python func/excel_production_enhanced.py <输入文件或文件夹>
python func/excel_merger.py <输入文件夹> <关键字> [--strip-time] [--sort '<json>']
```

如果希望使用项目环境运行，优先用 `uv run`：

```bash
uv run python func/excel_fuel.py <输入文件> --year 2025
```

### 测试

```bash
uv run pytest
uv run pytest tests/test_gui_components.py
uv run pytest tests/test_gui_components.py -k config
```

当前仓库只有 GUI 组件测试，主要覆盖 `gui/components.py` 与 `gui/main.py` 的行为。

## 高层架构

## 1. 两层业务组织：处理引擎 + GUI 编排

项目主体其实分成两层：

- `func/`：真正的 Excel 处理逻辑、配置读取、日志、设备台账。
- `gui/`：对 `func/` 中能力进行封装，负责收集用户输入、触发后台任务、展示日志与配置状态。

当你要修复数据问题时，通常应先看 `func/`；当你要改交互流程、按钮行为、日志展示，再看 `gui/`。

## 2. GUI 不是业务实现层，只是薄编排层

GUI 采用明显的三段式拆分：

- `gui/main.py`：组装页面、初始化全局日志、连接各分区。
- `gui/components.py`：只创建控件和局部状态，返回 `refs` 供外部操作。
- `gui/logic.py`：把按钮事件绑定到具体处理函数，并用 `asyncio.to_thread()` 把长耗时 Excel 处理放到后台线程执行。

这个分层很关键：

- **不要**把复杂 Excel 解析再塞回 `gui/components.py`。
- 新处理模块如果要接入 GUI，通常是：
  1. 在 `components.py` 增加输入控件；
  2. 在 `logic.py` 的 `_execute_task()` 和按钮回调中接入 `func/` 的处理函数；
  3. 在 `main.py` 里保持现有组装方式即可。

## 3. 日志流是 CLI 与 GUI 共享的基础设施

`func/logger.py` 提供统一日志格式；CLI 脚本直接调用 `setup_logging()` 输出到控制台。

GUI 侧在 `gui/main.py` 中额外挂载 `QueueHandler`，把后台线程里的日志推送到页面日志列表。因此：

- `func/` 中新增处理逻辑时，优先继续使用 `logging` / `get_logger()`，不要改成 `print()`。
- 只要处理函数里正常打日志，CLI 和 GUI 都能看到结果，不需要分别实现两套日志逻辑。

## 4. 处理脚本是彼此独立的，不共享统一领域模型

当前并不是一个统一的数据管道，而是多个相互独立的报表解析器：

- `excel_fuel.py`：从“设备柴油消耗”类表提取发动机与油耗信息，输出 `Fuel.xlsx`。
- `excel_electrical.py`：扫描包含 `Electrical` 的 sheet，按“日期”行定位列，再提取设备电耗。
- `excel_worktime.py`：输出按年月命名的工作效率表。
- `excel_production.py` / `excel_production_enhanced.py`：解析白班/夜班生产报表；enhanced 版是 GUI 默认使用版本。
- `excel_merger.py`：按文件名关键字批量合并同结构 Excel，并支持排序与日期格式化。

这意味着改动某个处理器时，要先确认它是否被 GUI 调用：GUI 当前通过 `gui/logic.py` 使用的是：

- `process_diesel_data`
- `MiningDataProcessor`（来自 `excel_production_enhanced.py`）
- `parse_excel_data`
- `process_excel_data`
- `merge_excel_files`

## 5. 配置分为“持久化默认值”和“运行时临时值”

`func/config_loader.py` 的行为要特别注意：

- `load_config()` / `save_config()` 读写内置 `config.json`。
- `apply_device_load_map()` **只更新当前运行时内存配置，不落盘**。
- `update_device_load_map()` 才会把配置写回文件。

GUI 里的“应用当前配置”和“保存配置”语义不同，修改相关代码时不要混淆，否则测试会失败。

## 6. 设备台账与模糊匹配目前是预备能力

`func/equipment_ledger.py` 已实现：

- 台账模板导出
- 台账 Excel 导入
- 标准名称 / 别名 / 前缀 / rapidfuzz 相似度匹配

但这套能力目前主要停留在 GUI 的台账管理区域，以及未来多表联动/名称归一化场景中。若要实现跨报表汇总，优先复用这里的 `EquipmentLedger.match()`，不要在别处重复造一套模糊匹配逻辑。

## 7. 未来多表联动的自然扩展点

仓库已经有“多表联动”的方向说明，现有代码里最接近该目标的基础设施是：

- `equipment_ledger.py`：设备名称标准化
- `config_loader.py`：设备型号到装载量映射
- 各 Excel 处理器的标准输出列（日期、班次、设备名及指标）
- `excel_merger.py`：多文件批量整合

如果后续要做综合统计报表，建议把新逻辑放在 `func/` 内新增独立模块，由 GUI/CLI 作为外层入口调用，而不是直接耦合进现有某个单一处理脚本。

## 测试与修改提示

- 现有测试集中在 `tests/test_gui_components.py`，很多断言围绕 GUI 间距、按钮行为、配置是否落盘、日志线程分发方式。
- 改 `gui/components.py`、`gui/main.py`、`func/config_loader.py` 时，优先跑该测试文件。
- 该仓库当前没有 lint/format 配置；不要在 `CLAUDE.md` 中假设存在 `ruff`、`black`、`mypy` 或 CI 命令。
