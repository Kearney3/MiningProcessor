# CLAUDE.md

本项目的开发约定和架构说明统一维护在 [AGENTS.md](AGENTS.md)。当前桌面应用使用 Tauri + React + TypeScript，Python 业务逻辑由 `func/` 提供，`tauri_bridge.py` 负责 JSON-RPC 桥接。

修改数据处理时从 `func/` 入手；修改桌面交互时从 `src/`、`src-tauri/` 和 bridge 调用链入手。不要在前端或 Rust 宿主中重复实现 Excel 业务规则。
