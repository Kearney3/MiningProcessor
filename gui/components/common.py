"""GUI 组件共享工具函数与状态"""
import flet as ft
import logging
from pathlib import Path

# 共享的文件选择器上次目录，所有模块复用同一份
# 使用列表以便在各模块内原地更新，保证跨模块可见
_last_directory: list[str] = [""]


def _log_message(log, message: str, level: int = logging.INFO):
    """兼容仅接收 message 的旧回调，也支持显式日志级别。"""
    try:
        log(message, level=level)
    except TypeError:
        log(message)


def _update_last_directory(path: str) -> None:
    """统一更新共享的文件选择器目录。"""
    _last_directory[0] = str(Path(path).parent)


class SortState:
    """排序状态管理"""
    def __init__(self):
        self.column: str | None = None
        self.ascending: bool = True

    def toggle(self, column: str):
        """切换排序列或方向"""
        if self.column == column:
            self.ascending = not self.ascending
        else:
            self.column = column
            self.ascending = True

    def reset(self):
        """重置排序状态"""
        self.column = None
        self.ascending = True

    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """对 DataFrame 应用排序"""
        if self.column and self.column in df.columns:
            try:
                return df.sort_values(by=self.column, ascending=self.ascending, kind="stable")
            except Exception:
                pass
        return df

    def get_column_index(self, columns: list[str]) -> int | None:
        """获取排序列的索引"""
        if self.column and self.column in columns:
            return columns.index(self.column)
        return None


def create_sortable_columns(
    columns: list[str],
    sort_state: SortState,
    on_sort_callback,
    text_size: int = 13,
) -> list[ft.DataColumn]:
    """创建可排序的列"""
    def on_sort_handler(col_idx):
        def handler(e):
            sort_state.toggle(columns[e.column_index])
            on_sort_callback()
        return handler

    return [
        ft.DataColumn(
            ft.Text(c, size=text_size, no_wrap=True),
            on_sort=on_sort_handler(c),
        )
        for c in columns
    ]


