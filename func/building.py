"""维修记录统计 DataFrame 构建

从分类后的维修记录构建 8 个统计 DataFrame，按文档 docs/维修记录统计.md 定义。
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


def _month_key(dt: date) -> str:
    """返回 YYYY-MM 格式的月份字符串。"""
    return f"{dt.year}-{dt.month:02d}"


def _all_major_categories(fault_records: list[dict]) -> list[str]:
    """按大类总分钟数降序返回所有出现的大类。"""
    major_minutes: dict[str, int] = defaultdict(int)
    for rec in fault_records:
        major_minutes[rec["大类"]] += _safe_minutes(rec["工时_分钟"])
    return [m for m, _ in sorted(major_minutes.items(), key=lambda x: -x[1])]


# ── 主构建函数 ────────────────────────────────────────────────

def build_sheets(
    classified: list[dict],
    fault_records: list[dict],
) -> dict[str, pd.DataFrame]:
    """从分类记录构建 8 个统计 DataFrame。"""
    sheets: dict[str, pd.DataFrame] = {}

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

    # ── 所有出现的大类（用于动态列展开）──
    majors = _all_major_categories(fault_records)

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
            "维修工时（分钟）": rec["工时_分钟"],
        })
    sheets["维修明细"] = pd.DataFrame(detail_rows)

    # ── Sheet 2: 每月设备故障统计 ──
    # 每台设备×月的故障概览，含各大类子列
    monthly_dev_stats: dict[tuple, dict] = defaultdict(lambda: {
        "count": 0, "minutes": 0, "fault_days": set(),
        "major_days": defaultdict(set),
        "major_minutes": defaultdict(int),
    })
    for rec in fault_records:
        if not rec["日期"]:
            continue
        mk = _month_key(rec["日期"])
        key = (mk, rec["标准设备名称"])
        s = monthly_dev_stats[key]
        s["model"] = rec["设备型号"]
        s["count"] += 1
        s["minutes"] += _safe_minutes(rec["工时_分钟"])
        s["fault_days"].add(rec["日期"].day)
        s["major_days"][rec["大类"]].add(rec["日期"].day)
        s["major_minutes"][rec["大类"]] += _safe_minutes(rec["工时_分钟"])

    sheet2_rows = []
    for (mk, v), s in sorted(monthly_dev_stats.items()):
        y, m = mk.split("-")
        import calendar
        month_total_days = calendar.monthrange(int(y), int(m))[1]
        rate = s["minutes"] / (month_total_days * 24 * 60) if month_total_days else 0
        row = {
            "月份": mk,
            "标准设备名称": v,
            "设备型号": s["model"],
            "有故障日数": len(s["fault_days"]),
            "总故障分钟": s["minutes"],
            "总故障小时": round(s["minutes"] / 60, 1),
            "故障率": rate,
        }
        for maj in majors:
            md = s["major_days"][maj]
            mm = s["major_minutes"][maj]
            row[f"{maj}(故障日数)"] = len(md)
            row[f"{maj}(总故障分钟)"] = mm
            row[f"{maj}(故障占比)"] = mm / s["minutes"] if s["minutes"] else 0
        sheet2_rows.append(row)
    sheets["每月设备故障统计"] = pd.DataFrame(sheet2_rows)

    # ── Sheet 3: 全周期设备故障统计（按月聚合）──
    # 每台设备的全周期故障概览，含各月子列 → 按设备名聚合，但包含月度维度
    # 实际上是每台设备的生命周期统计，保留月份为粒度
    lifecycle_dev: dict[str, dict] = defaultdict(lambda: {
        "min_date": None, "max_date": None, "count": 0, "minutes": 0,
        "fault_days": set(),
        "major_days": defaultdict(set),
        "major_minutes": defaultdict(int),
    })
    for rec in fault_records:
        v = rec["标准设备名称"]
        d = rec["日期"]
        if not d:
            continue
        ls = lifecycle_dev[v]
        ls["model"] = rec["设备型号"]
        ls["count"] += 1
        ls["minutes"] += _safe_minutes(rec["工时_分钟"])
        ls["fault_days"].add(d)
        ls["major_days"][rec["大类"]].add(d)
        ls["major_minutes"][rec["大类"]] += _safe_minutes(rec["工时_分钟"])

    sheet3_rows = []
    for v, ls in sorted(lifecycle_dev.items()):
        # 从全量记录取首末日期
        dd = device_dates.get(v, {})
        min_d, max_d = dd.get("min_date"), dd.get("max_date")
        total_days = _total_span_days(min_d, max_d)
        rate = ls["minutes"] / (total_days * 24 * 60) if total_days else 0
        row = {
            "月份": f"{min_d.year}-{min_d.month:02d}~{max_d.year}-{max_d.month:02d}" if min_d and max_d else "",
            "标准设备名称": v,
            "设备型号": ls["model"],
            "统计开始日期": min_d,
            "统计结束日期": max_d,
            "总日数": total_days,
            "有故障日数": len(ls["fault_days"]),
            "总故障分钟": ls["minutes"],
            "总故障小时": round(ls["minutes"] / 60, 1),
            "故障率": rate,
        }
        for maj in majors:
            md = ls["major_days"][maj]
            mm = ls["major_minutes"][maj]
            row[f"{maj}(故障日数)"] = len(md)
            row[f"{maj}(总故障分钟)"] = mm
            row[f"{maj}(故障占比)"] = mm / ls["minutes"] if ls["minutes"] else 0
        sheet3_rows.append(row)
    sheets["全周期设备故障统计"] = pd.DataFrame(sheet3_rows)

    # ── Sheet 4: 全周期设备故障汇总（设备×大类×小类）──
    dev_sub_stats: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "model": ""}
    )
    dev_major_minutes: dict[str, int] = defaultdict(int)
    dev_total_minutes: dict[str, int] = defaultdict(int)
    for rec in fault_records:
        key = (rec["标准设备名称"], rec["大类"], rec["小类"])
        ds = dev_sub_stats[key]
        ds["model"] = rec["设备型号"]
        ds["count"] += 1
        mins = _safe_minutes(rec["工时_分钟"])
        ds["minutes"] += mins
        dev_major_minutes[rec["标准设备名称"] + "|" + rec["大类"]] += mins
        dev_total_minutes[rec["标准设备名称"]] += mins

    # 每台设备的有效记录天数
    dev_record_days: dict[str, set] = defaultdict(set)
    for rec in classified:
        if rec["日期"]:
            dev_record_days[rec["标准设备名称"]].add(rec["日期"])

    sheet4_rows = []
    for (v, major, minor), ds in sorted(dev_sub_stats.items(), key=lambda x: (x[0][0], x[0][1], -x[1]["minutes"])):
        min_d, max_d = _device_date_range(device_dates, v)
        total_days = _total_span_days(min_d, max_d)
        major_mins = dev_major_minutes.get(f"{v}|{major}", 1)
        dev_mins = dev_total_minutes.get(v, 1)
        row = {
            "标准设备名称": v,
            "设备型号": ds["model"],
            "有效记录天数": len(dev_record_days.get(v, set())),
            "大类": major,
            "小类": minor,
            "总故障分钟": ds["minutes"],
            "总故障小时": round(ds["minutes"] / 60, 1),
            "故障率": _fault_rate(ds["minutes"], min_d, max_d),
            "小类故障占比": ds["minutes"] / major_mins if major_mins else 0,
            "大类故障占比": ds["minutes"] / dev_mins if dev_mins else 0,
        }
        sheet4_rows.append(row)
    sheets["全周期设备故障汇总"] = pd.DataFrame(sheet4_rows)

    # ── Sheet 5: 每月设备型号故障统计 ──
    monthly_model: dict[tuple, dict] = defaultdict(lambda: {
        "count": 0, "minutes": 0, "devices": set(), "fault_days": set(),
        "major_days": defaultdict(set),
        "major_minutes": defaultdict(int),
    })
    for rec in fault_records:
        if not rec["日期"]:
            continue
        mk = _month_key(rec["日期"])
        key = (mk, rec["设备型号"])
        ms = monthly_model[key]
        ms["count"] += 1
        ms["minutes"] += _safe_minutes(rec["工时_分钟"])
        ms["devices"].add(rec["标准设备名称"])
        ms["fault_days"].add(rec["日期"].day)
        ms["major_days"][rec["大类"]].add(rec["日期"].day)
        ms["major_minutes"][rec["大类"]] += _safe_minutes(rec["工时_分钟"])

    sheet5_rows = []
    for (mk, model), ms in sorted(monthly_model.items()):
        y, m = mk.split("-")
        import calendar
        month_total_days = calendar.monthrange(int(y), int(m))[1]
        rate = ms["minutes"] / (month_total_days * 24 * 60) if month_total_days else 0
        row = {
            "月份": mk,
            "设备型号": model,
            "有效台数": len(ms["devices"]),
            "有故障日数": len(ms["fault_days"]),
            "总故障分钟": ms["minutes"],
            "总故障小时": round(ms["minutes"] / 60, 1),
            "故障率": rate,
        }
        for maj in majors:
            md = ms["major_days"][maj]
            mm = ms["major_minutes"][maj]
            row[f"{maj}(故障日数)"] = len(md)
            row[f"{maj}(总故障分钟)"] = mm
            row[f"{maj}(故障占比)"] = mm / ms["minutes"] if ms["minutes"] else 0
        sheet5_rows.append(row)
    sheets["每月设备型号故障统计"] = pd.DataFrame(sheet5_rows)

    # ── Sheet 6: 全周期设备型号故障统计 ──
    lifecycle_model: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "minutes": 0, "devices": set(), "fault_days": set(),
        "major_days": defaultdict(set),
        "major_minutes": defaultdict(int),
    })
    for rec in fault_records:
        model = rec["设备型号"]
        d = rec["日期"]
        if not d:
            continue
        ls = lifecycle_model[model]
        ls["count"] += 1
        ls["minutes"] += _safe_minutes(rec["工时_分钟"])
        ls["devices"].add(rec["标准设备名称"])
        ls["fault_days"].add(d)
        ls["major_days"][rec["大类"]].add(d)
        ls["major_minutes"][rec["大类"]] += _safe_minutes(rec["工时_分钟"])

    sheet6_rows = []
    for model, ls in sorted(lifecycle_model.items()):
        model_total_days = sum(
            _total_span_days(*_device_date_range(device_dates, v))
            for v in ls["devices"]
        )
        model_total_minutes = model_total_days * 24 * 60 if model_total_days else 0
        rate = ls["minutes"] / model_total_minutes if model_total_minutes else 0
        row = {
            "设备型号": model,
            "有效台数": len(ls["devices"]),
            "总统计日数": model_total_days,
            "总故障天数": len(ls["fault_days"]),
            "总故障分钟": ls["minutes"],
            "总故障小时": round(ls["minutes"] / 60, 1),
            "故障率": rate,
        }
        for maj in majors:
            md = ls["major_days"][maj]
            mm = ls["major_minutes"][maj]
            row[f"{maj}(故障日数)"] = len(md)
            row[f"{maj}(总故障分钟)"] = mm
            row[f"{maj}(故障占比)"] = mm / ls["minutes"] if ls["minutes"] else 0
        sheet6_rows.append(row)
    sheets["全周期设备型号故障统计"] = pd.DataFrame(sheet6_rows)

    # ── Sheet 7: 全周期设备故障汇总（型号×大类×小类）──
    model_sub_stats: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "devices": set()}
    )
    model_major_minutes: dict[str, int] = defaultdict(int)
    model_total_minutes: dict[str, int] = defaultdict(int)
    for rec in fault_records:
        key = (rec["设备型号"], rec["大类"], rec["小类"])
        ms = model_sub_stats[key]
        ms["count"] += 1
        mins = _safe_minutes(rec["工时_分钟"])
        ms["minutes"] += mins
        ms["devices"].add(rec["标准设备名称"])
        model_major_minutes[rec["设备型号"] + "|" + rec["大类"]] += mins
        model_total_minutes[rec["设备型号"]] += mins

    sheet7_rows = []
    for (model, major, minor), ms in sorted(model_sub_stats.items(), key=lambda x: (x[0][0], x[0][1], -x[1]["minutes"])):
        model_total_days = sum(
            _total_span_days(*_device_date_range(device_dates, v))
            for v in ms["devices"]
        )
        major_mins = model_major_minutes.get(f"{model}|{major}", 1)
        mod_mins = model_total_minutes.get(model, 1)
        rate = ms["minutes"] / (model_total_days * 24 * 60) if model_total_days else 0
        sheet7_rows.append({
            "设备型号": model,
            "有效台数": len(ms["devices"]),
            "总记录天数": model_total_days,
            "总故障天数": 0,
            "大类": major,
            "小类": minor,
            "总故障分钟": ms["minutes"],
            "总故障小时": round(ms["minutes"] / 60, 1),
            "故障率": rate,
            "小类故障占比": ms["minutes"] / major_mins if major_mins else 0,
            "大类故障占比": ms["minutes"] / mod_mins if mod_mins else 0,
        })
    sheets["全周期设备型号故障汇总"] = pd.DataFrame(sheet7_rows)

    # ── Sheet 8: 故障类型统计 ──
    type_stats: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "minutes": 0}
    )
    month_major_minutes: dict[tuple, int] = defaultdict(int)
    month_total_minutes: dict[str, int] = defaultdict(int)
    for rec in fault_records:
        if not rec["日期"]:
            continue
        mk = _month_key(rec["日期"])
        key = (mk, rec["大类"], rec["小类"])
        ts = type_stats[key]
        mins = _safe_minutes(rec["工时_分钟"])
        ts["count"] += 1
        ts["minutes"] += mins
        month_major_minutes[(mk, rec["大类"])] += mins
        month_total_minutes[mk] += mins

    sheet8_rows = []
    for (mk, major, minor), ts in sorted(type_stats.items(), key=lambda x: (x[0][0], x[0][1], -x[1]["minutes"])):
        major_mins = month_major_minutes.get((mk, major), 1)
        month_mins = month_total_minutes.get(mk, 1)
        row = {
            "年月": mk,
            "大类": major,
            "小类": minor,
            "记录数": ts["count"],
            "维修工时（分钟）": ts["minutes"],
            "维修工时（小时）": round(ts["minutes"] / 60, 1),
            "占大类比": ts["minutes"] / major_mins if major_mins else 0,
            "占总故障时间比例": ts["minutes"] / month_mins if month_mins else 0,
            "大类故障占比": major_mins / month_mins if month_mins else 0,
        }
        sheet8_rows.append(row)
    sheets["故障类型统计"] = pd.DataFrame(sheet8_rows)

    return sheets
