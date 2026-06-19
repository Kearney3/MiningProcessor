"""
MineBase 数据同步脚本（向后兼容入口）

此文件是 func.sync 包的薄封装层，保留原有 import 路径。
实际逻辑已拆分至 func/sync/ 包下：
  - constants.py：常量定义
  - api_client.py：MineBaseAPIClient
  - db_client.py：MineBaseDBClient
  - file_processors.py：文件处理器与行数据辅助函数
  - core.py：主流程、CLI、连接测试
"""
from func.sync import *  # noqa: F401,F403
