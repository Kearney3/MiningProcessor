"""维修记录统计 DataFrame 构建

从分类后的维修记录构建 10 个统计 DataFrame。
"""
from collections import defaultdict
from datetime import date

import pandas as pd


# ── 辅助函数 ──────────────────────────────────────────────────

def _safe_minutes(val) -> int:
    """安全取工时分钟数，None/NaN/异常值 → 0。"""
    if val is None:
        return 0
    if isinstance(val, float) and pd.isna(val):
        return 0
    try:
        return max(0, int(val))
    except (ValueError, TypeError):
        return 0


def _device_date_range(
    device_dates: dict[str, dict], device_name: str
) -> tuple[date | None, date | None]:
    """获取设备的统计日期范围。"""
    dd = device_dates.get(device_name, {})
    return dd.get("min_date"), dd.get("max_date")


def _total_span_days(min_d: date | None, max_d: date | None) -> int:
    """计算日期跨度天数。"""
    return (max_d - min_d).days + 1 if min_d and max_d else 0


def _fault_rate(minutes: int, min_d: date | None, max_d: date | None) -> float:
    """计算故障率（故障分钟 / 总统计分钟）。"""
    total_days = _total_span_days(min_d, max_d)
    total_minutes = total_days * 24 * 60 if total_days else 0
    return minutes / total_minutes if total_minutes else 0


# ── 主构建函数 ────────────────────────────────────────────────

def build_sheets(
    classified: list[dict],
    fault_records: list[dict],
) -> dict[str, pd.DataFrame]:
    """从分类记录构建 10 个统计 DataFrame。"""
    sheets: dict[str, pd.DataFrame] = {}

    # ── Sheet 1: 维修明细 ──
    detail_rows = []
    for rec in classified:
        detail_rows.append({
            "日期": rec["日期"],
            "原始设备名称": rec["原始设备名称"],
            "标准设备名称": rec["标准设备名称"],
            "设备型号": rec["设备型号"],
            "原因": rec["原因"],
            "班次": rec["班次"],
            "大类": rec["大类"] or "",
            "小类": rec["小类"] or "",
            "是否故障": rec["是否故障"],
            "维修内容": rec["维修内容"],
            "工时_分钟": rec["工时_分钟"],
        })
    sheets["维修明细"] = pd.DataFrame(detail_rows)

    # ── 设备日期范围（全量记录用于计算统计跨度）──
    device_dates: dict[str, dict] = defaultdict(
        lambda: {"min_date": None, "max_date": None}
    )
    for rec in classified:
        v = rec["标准设备名称"]
        d = rec["日期"]
        if v and d:
            info = device_dates[v]
            if info["min_date"] is None or d < info["min_date"]:
                info["min_date"] = d
            if info["max_date"] is None or d > info["max_date"]:
                info["max_date"] = d

    # ── Sheet 2: 大类汇总（仅故障记录）──
    major_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "minutes": 0})
    for rec in fault_records:
        major_stats[rec["大类"]]["count"] += 1
        major_stats[rec["大类"]]["minutes"] += _safe_minutes(rec["工时_分钟"])
    total_fault_count = len(fault_records)
    total_fault_minutes = sum(s["minutes"] for s in major_stats.values())

    major_rows = []
    for major, s in sorted(major_stats.items(), key=lambda x: -x[1]["count"]):
        major_rows.append({
            "大类": major,
            "记录数": s["count"],
            "工时_分钟": s["minutes"],
            "工时_小时": round(s["minutes"] / 60, 1),
            "占比(记录)": s["count"] / total_fault_count if total_fault_count else 0,
            "占比(工时)": s["minutes"] / total_fault_minutes if total_fault_minutes else 0,
        })
    # 合计行
    major_rows.append({
        "大类": "合计",
        "记录数": total_fault_count,
        "工时_分钟": total_fault_minutes,
        "工时_小时": round(total_fault_minutes / 60, 1),
        "占比(记录)": 1.0,
        "占比(工时)": 1.0,
    })
    sheets["大类汇总"] = pd.DataFrame(major_rows)

    # ── Sheet 3: 大类×小类 ──
    sub_stats: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "minutes": 0})
    major_totals: dict[str, int] = defaultdict(int)
    for rec in fault_records:
        key = (rec["大类"], rec["小类"])
        sub_stats[key]["count"] += 1
        sub_stats[key]["minutes"] += _safe_minutes(rec["工时_分钟"])
        major_totals[rec["大类"]] += 1

    sub_rows = []
    for (major, minor), s in sorted(sub_stats.items(), key=lambda x: (x[0][0], -x[1]["count"])):
        sub_rows.append({
            "大类": major,
            "小类": minor,
            "记录数": s["count"],
            "工时_分钟": s["minutes"],
            "工时_小时": round(s["minutes"] / 60, 1),
            "占大类比": s["count"] / major_totals[major] if major_totals[major] else 0,
        })
    sheets["大类×小类"] = pd.DataFrame(sub_rows)

    # ── Sheet 4: 按设备统计 ──
    dev_stats: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "days": set(), "model": ""}
    )
    for rec in fault_records:
        v = rec["标准设备名称"]
        ds = dev_stats[v]
        ds["model"] = rec["设备型号"]
        ds["count"] += 1
        ds["minutes"] += _safe_minutes(rec["工时_分钟"])
        if rec["日期"]:
            ds["days"].add(rec["日期"])

    dev_rows = []
    for v, ds in sorted(dev_stats.items()):
        min_d, max_d = _device_date_range(device_dates, v)
        dev_rows.append({
            "设备型号": ds["model"],
            "标准设备名称": v,
            "统计开始日期": min_d,
            "统计结束日期": max_d,
            "总日数": _total_span_days(min_d, max_d),
            "有故障日数": len(ds["days"]),
            "总故障分钟": ds["minutes"],
            "总故障小时": round(ds["minutes"] / 60, 1),
            "故障率": _fault_rate(ds["minutes"], min_d, max_d),
        })
    sheets["按设备统计"] = pd.DataFrame(dev_rows)

    # ── Sheet 5: 按设备型号统计 ──
    model_stats: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "devices": set(), "fault_days": set()}
    )
    for rec in fault_records:
        model = rec["设备型号"]
        ms = model_stats[model]
        ms["count"] += 1
        ms["minutes"] += _safe_minutes(rec["工时_分钟"])
        ms["devices"].add(rec["标准设备名称"])
        if rec["日期"]:
            ms["fault_days"].add(rec["日期"])

    model_rows = []
    for model, ms in sorted(model_stats.items()):
        model_total_days = sum(
            _total_span_days(*_device_date_range(device_dates, v))
            for v in ms["devices"]
        )
        model_total_minutes = model_total_days * 24 * 60 if model_total_days else 0
        rate = ms["minutes"] / model_total_minutes if model_total_minutes else 0
        model_rows.append({
            "设备型号": model,
            "台数": len(ms["devices"]),
            "总统计日数": model_total_days,
            "总故障分钟": ms["minutes"],
            "总故障小时": round(ms["minutes"] / 60, 1),
            "有故障日数": len(ms["fault_days"]),
            "总故障次数": ms["count"],
            "故障率": rate,
        })
    sheets["按设备型号统计"] = pd.DataFrame(model_rows)

    # ── Sheet 6: 大类×年月 ──
    month_stats: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "minutes": 0})
    for rec in fault_records:
        key = (rec["大类"], rec["日期"].year, rec["日期"].month) if rec["日期"] else None
        if key:
            month_stats[key]["count"] += 1
            month_stats[key]["minutes"] += _safe_minutes(rec["工时_分钟"])

    month_rows = []
    for (major, y, m), s in sorted(month_stats.items()):
        month_rows.append({
            "大类": major,
            "年月": f"{y}-{m:02d}",
            "记录数": s["count"],
            "工时_分钟": s["minutes"],
            "工时_小时": round(s["minutes"] / 60, 1),
        })
    sheets["大类×年月"] = pd.DataFrame(month_rows)

    # ── Sheet 7: 设备名称×大类小类 ──
    dev_sub_stats: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "minutes": 0, "model": ""})
    for rec in fault_records:
        key = (rec["标准设备名称"], rec["大类"], rec["小类"])
        ds = dev_sub_stats[key]
        ds["model"] = rec["设备型号"]
        ds["count"] += 1
        ds["minutes"] += _safe_minutes(rec["工时_分钟"])

    dev_sub_rows = []
    for (v, major, minor), ds in sorted(dev_sub_stats.items(), key=lambda x: (x[0][0], -x[1]["count"])):
        min_d, max_d = _device_date_range(device_dates, v)
        dev_sub_rows.append({
            "设备型号": ds["model"],
            "标准设备名称": v,
            "大类": major,
            "小类": minor,
            "总故障分钟": ds["minutes"],
            "总故障小时": round(ds["minutes"] / 60, 1),
            "故障率": _fault_rate(ds["minutes"], min_d, max_d),
        })
    sheets["设备名称×大类小类"] = pd.DataFrame(dev_sub_rows)

    # ── Sheet 8: 型号×大类小类 ──
    model_sub_stats: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "devices": set(), "fault_days": set()}
    )
    for rec in fault_records:
        key = (rec["设备型号"], rec["大类"], rec["小类"])
        ms = model_sub_stats[key]
        ms["count"] += 1
        ms["minutes"] += _safe_minutes(rec["工时_分钟"])
        ms["devices"].add(rec["标准设备名称"])
        if rec["日期"]:
            ms["fault_days"].add(rec["日期"])

    model_sub_rows = []
    for (model, major, minor), ms in sorted(model_sub_stats.items()):
        model_total_days = sum(
            _total_span_days(*_device_date_range(device_dates, v))
            for v in ms["devices"]
        )
        model_total_minutes = model_total_days * 24 * 60 if model_total_days else 0
        rate = ms["minutes"] / model_total_minutes if model_total_minutes else 0
        model_sub_rows.append({
            "设备型号": model,
            "大类": major,
            "小类": minor,
            "台数": len(ms["devices"]),
            "总统计日数": model_total_days,
            "总故障分钟": ms["minutes"],
            "总故障小时": round(ms["minutes"] / 60, 1),
            "故障率": rate,
        })
    sheets["型号×大类小类"] = pd.DataFrame(model_sub_rows)

    # ── Sheet 9: 设备名称×原因 ──
    reason_stats: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "days": set(), "model": ""}
    )
    for rec in fault_records:
        key = (rec["标准设备名称"], rec["原因"])
        rs = reason_stats[key]
        rs["model"] = rec["设备型号"]
        rs["count"] += 1
        rs["minutes"] += _safe_minutes(rec["工时_分钟"])
        if rec["日期"]:
            rs["days"].add(rec["日期"])

    reason_rows = []
    for (v, reason), rs in sorted(reason_stats.items(), key=lambda x: (x[0][0], -x[1]["count"])):
        min_d, max_d = _device_date_range(device_dates, v)
        reason_rows.append({
            "设备型号": rs["model"],
            "标准设备名称": v,
            "原因": reason,
            "故障次数": rs["count"],
            "统计开始日期": min_d,
            "统计结束日期": max_d,
            "总日数": _total_span_days(min_d, max_d),
            "有故障日数": len(rs["days"]),
            "总故障分钟": rs["minutes"],
            "总故障小时": round(rs["minutes"] / 60, 1),
            "故障率": _fault_rate(rs["minutes"], min_d, max_d),
        })
    sheets["设备名称×原因"] = pd.DataFrame(reason_rows)

    # ── Sheet 10: 发动机故障深挖 ──
    engine_rows = []
    for rec in classified:
        if rec["大类"] != "发动机" or rec["是否故障"] != "是":
            continue
        engine_rows.append({
            "设备型号": rec["设备型号"],
            "标准设备名称": rec["标准设备名称"],
            "日期": rec["日期"],
            "小类": rec["小类"] or "",
            "班次": rec["班次"],
            "维修内容": rec["维修内容"],
            "工时_分钟": rec["工时_分钟"],
        })
    engine_rows.sort(key=lambda r: (r["设备型号"], r["标准设备名称"], r["日期"]))
    sheets["发动机故障深挖"] = pd.DataFrame(engine_rows)

    return sheets
