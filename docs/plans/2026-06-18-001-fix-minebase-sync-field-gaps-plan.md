---
title: "fix: 补齐 MiningProcessor → MineBase 数据同步字段缺口"
type: fix
date: 2026-06-18
---

# fix: 补齐 MiningProcessor → MineBase 数据同步字段缺口

## Summary

MiningProcessor 的 MineBase 同步功能整体架构对齐（5 表、去重约束、FK 解析、API 三步协议），但存在 4 处字段级缺口需要修复：`remark` 未映射、`equipment_operation` 缺 `company`、`electricity_consumption` 缺 `shiftType` 默认值、以及测试覆盖不足。

## Problem Frame

MiningProcessor 处理 Excel 后通过 `func/sync_to_minebase.py` 同步到 MineBase。MineBase 近期经历了多次 schema 迁移（自然键唯一约束、`brand` → `company` 列重命名、`remark` 列添加），MiningProcessor 的列映射配置和同步逻辑未完全跟上这些变化。

关键约束：`equipmentCode` 允许缺失（MineBase 服务端有处理逻辑）；`sourceLocation`/`destLocation` 不在同步范围内。

## Requirements

**字段映射补齐**

- R1. `minebase_column_mapping` 中为 `equipment_operation` 和 `production_record` 添加 `备注` → `remark` 映射
- R2. `minebase_column_mapping` 中为 `equipment_operation` 添加 `公司` → `company` 映射

**电气数据班次默认值**

- R3. 同步 `electricity_consumption` 时，若 Excel 数据不含 `shiftType` 字段，自动填充默认值 `"Night"`

**测试**

- R4. 更新测试覆盖上述三项变更，验证映射完整性和默认值行为

## Key Technical Decisions

**KTD1. `shiftType` 默认值注入位置选在 `sync_via_api` / `sync_via_db` 入口处。** 不修改 `read_and_map_excel`（它是通用函数，不应包含业务默认值逻辑），而是在各 sync 函数入口针对 `electricity_consumption` 类型做行级补全。

**KTD2. `remark` 映射仅限有该列的 Excel 输出。** `fuel_consumption`（油耗信息 sheet）和 `electricity_consumption` 的 Excel 输出不含`备注`列，不添加映射。仅对 `equipment_operation`（运行数据 sheet 2 有`备注`）和 `production_record` 添加映射。

## Implementation Units

### U1. 补齐 `minebase_column_mapping` 配置

**Goal:** 在 `config.json` 的 `minebase_column_mapping` 中添加缺失的字段映射。

**Requirements:** R1, R2

**Files:**
- `config.json` — `minebase_column_mapping.equipment_operation` 和 `production_record` 段

**Approach:**
- `equipment_operation` 段追加：`"备注": "remark"`, `"公司": "company"`
- `production_record` 段追加：`"备注": "remark"`
- 注意：`work_efficiency` 段已有 `"注释": "remark"` 映射，无需修改

**Test scenarios:**
- Happy path: 加载配置后 `get_minebase_column_mapping()` 返回的 `equipment_operation` 映射包含 `remark` 和 `company` 键
- Happy path: `production_record` 映射包含 `remark` 键

**Verification:** `config.json` 中 `minebase_column_mapping` 各段字段与 `FIELD_TO_COLUMN_MAP` 中对应表的字段一致。

### U2. 电气同步默认班次填充

**Goal:** 当 `electricity_consumption` 数据缺少 `shiftType` 时，自动填充 `"Night"`。

**Requirements:** R3

**Dependencies:** U1（映射配置需先到位）

**Files:**
- `func/sync_to_minebase.py` — 新增 `_apply_defaults` 辅助函数，修改 `sync_via_api` 和 `sync_via_db` 调用处
- `tests/test_sync_to_minebase.py` — 新增默认班次测试

**Approach:**
- 新增 `_apply_defaults(rows, data_type)` 函数，对 `electrical` 类型的每行检查：若 `"shiftType"` 不在行数据中，则设置为 `"Night"`
- 在 `sync_via_api` 和 `sync_via_db` 入口、`read_and_map_excel` 返回后调用此函数
- 保持 `read_and_map_excel` 不变（通用函数不含业务逻辑）

**Test scenarios:**
- Happy path: 电气数据无 `shiftType` 列 → 同步后每行包含 `shiftType: "Night"`
- Happy path: 电气数据已有 `shiftType` 列 → 不覆盖原值
- Edge case: 非电气数据类型（如 fuel）→ 不注入默认值

**Verification:** 电气数据在缺少班次列时，API 模式和 DB 模式均正确填充 `"Night"`。

### U3. 更新测试覆盖

**Goal:** 确保所有变更均有测试覆盖，整体测试通过。

**Requirements:** R4

**Dependencies:** U1, U2

**Files:**
- `tests/test_sync_to_minebase.py`

**Approach:**
- 为 `_apply_defaults` 新增独立单元测试
- 验证映射配置加载后包含新增字段
- 跑全量测试确认无回归

**Test scenarios:**
- `_apply_defaults` 对 electrical 类型无 shiftType 行注入 "Night"
- `_apply_defaults` 对 electrical 类型有 shiftType 行不覆盖
- `_apply_defaults` 对非 electrical 类型无操作
- 映射配置加载后 `equipment_operation` 包含 `remark` 和 `company`
- 映射配置加载后 `production_record` 包含 `remark`

**Verification:** `uv run pytest tests/test_sync_to_minebase.py` 全部通过。

## Scope Boundaries

**Deferred to Follow-Up Work:**
- `equipmentCode` 字段缺失处理 — MineBase 服务端已有逻辑，当前不需要 MiningProcessor 侧修改
- `sourceLocation` / `destLocation` 映射 — 用户确认忽略

**Outside this plan:**
- 修改 Excel 处理器（`excel_fuel.py` 等）的输出列结构
- MineBase 侧的 schema 或 API 变更
