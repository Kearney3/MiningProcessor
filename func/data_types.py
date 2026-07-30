"""数据类型常量定义

统一供 Flet GUI、Tauri bridge 和前端使用的数据类型 ID 与标签映射。
"""

# MineBase 同步支持的数据类型
# (id, 中文标签)
SYNC_DATA_TYPES: list[tuple[str, str]] = [
    ("fuel", "油耗数据"),
    ("production", "生产数据"),
    ("electrical", "电力消耗"),
    ("work_efficiency", "工时数据"),
    ("operation", "设备运行"),
]

# 仅 id 列表
SYNC_DATA_TYPE_IDS: list[str] = [t[0] for t in SYNC_DATA_TYPES]

# id → 标签映射
SYNC_DATA_TYPE_LABELS: dict[str, str] = dict(SYNC_DATA_TYPES)
