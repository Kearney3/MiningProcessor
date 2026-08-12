"""统一的本地时区日期/时间工具。

业务日期（Excel 中的日期、日报筛选日期等）表示运行机器所在本地时区的
日历日期；日志、数据库更新时间等时间点使用带本地时区信息的 datetime。
不在这里固定某个地区，始终跟随操作系统的本地时区。
"""

from __future__ import annotations

from datetime import date, datetime, time


def local_now() -> datetime:
    """返回当前本地时间，并携带本地 UTC 偏移。"""

    return datetime.now().astimezone()


def local_today() -> date:
    """返回当前本地日历日期。"""

    return local_now().date()


def local_datetime_from_timestamp(timestamp: float) -> datetime:
    """将 Unix 时间戳转换为带本地时区信息的 datetime。"""

    return datetime.fromtimestamp(timestamp).astimezone()


def local_midnight(day: date) -> datetime:
    """将日期转换为本地时区的当天零点。

    主要供 Flet DatePicker 使用，避免 Flet 将 naive datetime 当作 UTC
    序列化后产生日期偏移。
    """

    return datetime.combine(day, time.min).astimezone()

