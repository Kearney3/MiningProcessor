"""维修记录分类引擎

提供故障判定、大类/小类分类、噪声过滤，以及 Excel 配置模板的导入/导出。
分类规则从 config.json 读取；配置为空时使用硬编码默认值。
"""
import logging
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

logger = logging.getLogger(__name__)


# ── 默认分类规则 ──────────────────────────────────────────────

_DEFAULT_CLASSIFICATIONS: list[dict] = [
    # ── 发动机 ──
    {"major": "发动机", "minor": "报警/故障灯", "keywords": ["发动机报警", "发动机黄灯", "发动机故障", "发动机故障代码"]},
    {"major": "发动机", "minor": "增压器故障", "keywords": ["增压器", "涡轮增压", "涡轮"]},
    {"major": "发动机", "minor": "内部机械故障", "keywords": ["拉缸", "曲轴", "止推瓦", "缸套", "活塞", "凸轮轴", "连杆", "缸垫", "气门"]},
    {"major": "发动机", "minor": "启动故障", "keywords": ["不着火", "着不了火", "着不了车", "启动不了", "启动不着", "启动困难", "起动机", "启动马达", "打不着", "盘动飞轮", "旋转飞轮", "转飞轮", "盘车", "撞击飞轮"]},
    {"major": "发动机", "minor": "动力不足", "keywords": ["没劲儿", "没劲", "无力"]},
    {"major": "发动机", "minor": "异响/冒烟", "keywords": ["异响", "有异响", "冒黑烟", "冒白烟", "冒蓝烟", "冒烟"]},
    {"major": "发动机", "minor": "漏油/渗油", "keywords": ["发动机漏油", "发动机渗油", "机油进柴油", "缸盖漏油"]},
    {"major": "发动机", "minor": "喷油系统", "keywords": ["喷油器", "喷油嘴", "高压泵", "共轨", "柴油泵"]},
    {"major": "发动机", "minor": "冷却系统故障", "keywords": ["水箱漏", "冷却液漏", "水温高", "水温报警"]},
    {"major": "发动机", "minor": "排气异常", "keywords": ["排气大", "下排气", "排温", "排气温度"]},
    {"major": "发动机", "minor": "ECM/ECU", "keywords": ["ECM", "ECU"]},
    {"major": "发动机", "minor": "发动机大修", "keywords": ["发动机维修", "维修发动机", "装发动机", "发动机大修", "大修"]},
    {"major": "发动机", "minor": "发动机通用", "keywords": ["发动机"]},
    # ── 变速箱 ──
    {"major": "变速箱", "minor": "报警", "keywords": ["变速箱报警", "变速箱故障"]},
    {"major": "变速箱", "minor": "漏油/渗油", "keywords": ["变速箱漏油", "变速箱渗油", "变速箱油冷却器"]},
    {"major": "变速箱", "minor": "换挡/离合器", "keywords": ["换挡", "挡位", "离合器", "倒挡", "不增档", "不减档"]},
    {"major": "变速箱", "minor": "变速箱保养", "keywords": ["变速箱油", "变速箱滤芯"]},
    {"major": "变速箱", "minor": "变速箱通用", "keywords": ["变速箱", "变矩器"]},
    # ── 液压系统 ──
    {"major": "液压系统", "minor": "液压泵/马达", "keywords": ["液压泵", "液压马达"]},
    {"major": "液压系统", "minor": "液压油缸", "keywords": ["油缸", "漏液压油", "液压油箱"]},
    {"major": "液压系统", "minor": "液压阀", "keywords": ["分配器", "溢流阀", "多路阀", "阀门"]},
    {"major": "液压系统", "minor": "液压通用", "keywords": ["液压"]},
    # ── 电气系统 ──
    {"major": "电气系统", "minor": "传感器", "keywords": ["传感器"]},
    {"major": "电气系统", "minor": "电瓶/电池", "keywords": ["电瓶", "电池"]},
    {"major": "电气系统", "minor": "发电机", "keywords": ["发电机", "电机"]},
    {"major": "电气系统", "minor": "线束/电线", "keywords": ["电线", "线束"]},
    {"major": "电气系统", "minor": "灯泡/灯光", "keywords": ["灯泡", "灯光"]},
    {"major": "电气系统", "minor": "显示器/控制器", "keywords": ["显示屏", "控制器", "电脑板", "IGBT"]},
    {"major": "电气系统", "minor": "喇叭/雨刷", "keywords": ["喇叭", "雨刷"]},
    {"major": "电气系统", "minor": "电气通用", "keywords": ["电气报警", "电气故障", "电气", "继电器", "保险丝"]},
    # ── 制动系统 ──
    {"major": "制动系统", "minor": "制动管路", "keywords": ["制动管", "制动压力管", "刹车管"]},
    {"major": "制动系统", "minor": "刹车报警", "keywords": ["刹车报警", "制动报警"]},
    {"major": "制动系统", "minor": "制动通用", "keywords": ["刹车", "制动", "驻车", "刹车片", "刹车盘"]},
    # ── 转向系统 ──
    {"major": "转向系统", "minor": "转向故障", "keywords": ["转向泵", "转向缸", "转向", "方向盘", "转向报警"]},
    # ── 悬挂/车架 ──
    {"major": "悬挂/车架", "minor": "悬挂油缸", "keywords": ["悬挂油缸", "悬挂漏油", "悬挂渗油"]},
    {"major": "悬挂/车架", "minor": "大梁/车架", "keywords": ["大梁", "车架", "支重轮", "托轮", "平衡梁"]},
    {"major": "悬挂/车架", "minor": "悬挂通用", "keywords": ["悬挂"]},
    # ── 轮胎/轮马达 ──
    {"major": "轮胎/轮马达", "minor": "轮马达报警", "keywords": ["轮马达报警", "电动轮报警", "轮马达"]},
    {"major": "轮胎/轮马达", "minor": "轮胎损伤", "keywords": ["轮胎花纹", "轮胎脱空", "轮胎漏气", "油封漏油", "背靠背"]},
    {"major": "轮胎/轮马达", "minor": "轮胎通用", "keywords": ["轮胎", "轮辋"]},
    # ── 润滑系统 ──
    {"major": "润滑系统", "minor": "润滑报警", "keywords": ["润滑报警"]},
    {"major": "润滑系统", "minor": "润滑管路", "keywords": ["润滑管", "润滑软管"]},
    {"major": "润滑系统", "minor": "润滑通用", "keywords": ["润滑"]},
    # ── 空调 ──
    {"major": "空调", "minor": "空调异响", "keywords": ["异响"]},
    {"major": "空调", "minor": "空调故障", "keywords": ["空调不工作", "空调没有", "空调异响", "空调"]},
    # ── 排气系统 ──
    {"major": "排气系统", "minor": "排气通用", "keywords": ["消声器", "排气管", "SCR", "DPF", "尿素", "排气管异响", "排气异响"]},
    # ── 事故/损失 ──
    {"major": "事故/损失", "minor": "资产损失", "keywords": ["资产损失", "报废", "财产损失", "烧车", "起火", "着火", "防火系统"]},
    {"major": "事故/损失", "minor": "碰撞/倾覆", "keywords": ["碰撞", "倾覆", "翻车"]},
    # ── 日常维护 ──
    {"major": "日常维护", "minor": "动力系统保养", "keywords": ["补加机油", "升机油", "加油", "机油"]},
    {"major": "日常维护", "minor": "轮胎更换", "keywords": ["换轮胎", "更换轮胎"]},
    {"major": "日常维护", "minor": "轮胎保养", "keywords": ["轮胎补气", "调节胎压", "补气", "氮气", "充氮气"]},
    {"major": "日常维护", "minor": "润滑系统保养", "keywords": ["加注黄油", "充黄油", "打点油", "打点润滑"]},
    {"major": "日常维护", "minor": "加制冷剂", "keywords": ["制冷剂", "冷却剂"]},
    {"major": "日常维护", "minor": "加注黄油", "keywords": ["补加黄油", "已充.*黄油", "已加注.*黄油", "公斤黄油", "黄油箱"]},
    {"major": "日常维护", "minor": "空滤", "keywords": ["滤芯", "吹清空滤", "空滤吹风", "吹空滤"]},
    {"major": "日常维护", "minor": "加注防冻液", "keywords": ["补加防冻液", "升防冻液"]},
    {"major": "日常维护", "minor": "液压油系统保养", "keywords": ["补加液压油", "升液压油"]},
    {"major": "日常维护", "minor": "保养", "keywords": ["小时保养"]},
]

_DEFAULT_NOISE_EXACT: set[str] = {
    "交接班",
    "停车",
    "出车",
    "出车。",
    "出车了",
    "升机油",
    "升防冻液",
    "启动检查",
    "均为正常",
    "夜班",
    "已吹清空滤",
    "已吹清空滤，出车",
    "已吹清空滤，出车。",
    "已点检",
    "已补加机油",
    "正常",
    "点检",
    "点检时",
    "白班",
    "着车",
    "着车，出车",
    "着车，出车。",
    "计划点检",
}

_DEFAULT_NOISE_PATTERNS: list[str] = [
    r"^已?点检[，,/\s]*正常[。]?\s*$",
    r"^Author:.*",
    r"^MTC Translator:",
    r"^[已点检正常，,/\s\.。]+$",
    r"^已吹清空滤[，,\s]*(出车)?[。]?\s*$",
    r"^(已点检|点检)[，,/\s]+.*正常.*$",
    r"^\d+\s*小时保养[，,\s]*.*$",
    r"^(白班|夜班)[：:]?\s*(已?点检)?[，,/\s]*正常[。]?\s*$",
    r"^(着车|搭接着车|外接电源启动)[，,\s]*出车[。]?\s*$",
    r"^(夜班|白班)[：:]?\s*$",
    r"^\d+PM\s*$",
    r"^计划点检[：:]?\s*(已?点检)?[，,/\s]*(正常)?[。]?\s*$",
    r"^(已点检|点检)[，,/\s]*(左侧|右侧)?[。]?\s*$",
    r"^(对设备)?进行检查[，,\s]*出车[。]?\s*$",
    r"^(等待配件|待配件|等待备件)[，,\s]*(停车)?[。]?\s*$",
    r"^打着\s*$",
    r"^已?充好?黄油[箱]?[。]?\s*$",
    r"^已?加注?\d*公斤黄油[箱]?[。]?\s*$",
    r"^(由)?ETT验车[，,\s]*停车[。]?\s*$",
]

_DEFAULT_REASON_RULES: dict[str, str] = {
    "检修": "fault",
    "点检": "check_content",
    "保养": "non_fault",
    "待机": "skip",
}


# ── Excel 模板样式 ────────────────────────────────────────────

_HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
_HEADER_FONT = Font(bold=True, size=11, color="FFFFFF")
_THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def _apply_header(cell):
    cell.font = _HEADER_FONT
    cell.fill = _HEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = _THIN_BORDER


def _set_cell(ws, row, col, val):
    cell = ws.cell(row=row, column=col, value=val)
    cell.border = _THIN_BORDER
    return cell


# ── 公开 API ──────────────────────────────────────────────────

def get_default_classifications() -> dict:
    """返回硬编码默认分类配置（完整 14 大类）。"""
    return {
        "classifications": [dict(c) for c in _DEFAULT_CLASSIFICATIONS],
        "noise_exact": set(_DEFAULT_NOISE_EXACT),
        "noise_patterns": list(_DEFAULT_NOISE_PATTERNS),
        "reason_rules": dict(_DEFAULT_REASON_RULES),
    }


def compile_noise_patterns(patterns: list[str]) -> list[re.Pattern]:
    """编译正则模式列表，跳过无效模式并记录警告。

    供调用方预编译一次后传入 is_fault_record / classify，避免每条记录重复编译。

    Args:
        patterns: 正则模式字符串列表。

    Returns:
        编译后的 re.Pattern 列表。
    """
    compiled = []
    for pat in patterns:
        try:
            compiled.append(re.compile(pat))
        except re.error:
            logger.warning("无效的噪声正则模式，已跳过: %s", pat)
    return compiled


def is_fault_record(
    reason: str,
    content: str,
    *,
    noise_exact: set[str] | None = None,
    noise_patterns: list[str] | None = None,
    compiled_noise: list[re.Pattern] | None = None,
    reason_rules: dict[str, str] | None = None,
) -> bool:
    """根据原因和维修内容判断是否为故障记录。

    Args:
        reason: 原因类型（检修/点检/保养/待机）。
        content: 维修内容文本。
        noise_exact: 精确匹配噪声集合，None 时使用默认值。
        noise_patterns: 正则噪声模式列表（字符串），None 时使用默认值。
            如果提供了 compiled_noise，则忽略此参数。
        compiled_noise: 预编译的噪声正则列表，优先于 noise_patterns 使用。
        reason_rules: 原因判定规则，None 时使用默认值。

    Returns:
        True 表示故障记录。
    """
    if noise_exact is None:
        noise_exact = _DEFAULT_NOISE_EXACT
    if reason_rules is None:
        reason_rules = _DEFAULT_REASON_RULES
    if compiled_noise is None:
        patterns = noise_patterns if noise_patterns is not None else _DEFAULT_NOISE_PATTERNS
        compiled_noise = compile_noise_patterns(patterns)

    rule = reason_rules.get(reason, "check_content")

    if rule == "skip":
        return False
    if rule == "non_fault":
        return False
    if rule == "fault":
        return True

    # check_content: 检查内容是否有实质故障描述
    if not content or content in noise_exact:
        return False
    for pat in compiled_noise:
        if pat.match(content.strip()):
            return False
    # 含"正常"且无其他实质描述 → 非故障
    if "正常" in content:
        cleaned = re.sub(r"[已点检，,/\s正常。\.]+", "", content)
        if len(cleaned.strip()) < 3:
            return False
    return True


def _group_by_major(classifications: list[dict]) -> dict[str, list[dict]]:
    """按大类分组，保留各组内原始顺序。

    Args:
        classifications: 分类规则列表。

    Returns:
        按大类分组的 OrderedDict，值为该大类下的规则列表（保持原顺序）。
    """
    grouped: dict[str, list[dict]] = {}
    for entry in classifications:
        major = entry["major"]
        grouped.setdefault(major, []).append(entry)
    return grouped


def _best_major(content: str, grouped: dict[str, list[dict]]) -> str | None:
    """从所有大选中选出最佳大类。

    评分规则（元组比较）：
      主指标 = 该大类下命中关键词的小类数量（entry_count）
      次指标 = 该大类下所有命中关键词中的最长字符数（max_keyword_len）
      两个指标均更高者胜出；平局时优先返回列表靠前的大类。

    Args:
        content: 维修内容文本。
        grouped: 按大类的分组数据（顺序保留）。

    Returns:
        最佳大类名称，无任何关键字匹配时返回 None。
    """
    best = None
    best_score = (0, 0)
    for major, entries in grouped.items():
        entry_count = 0
        max_len = 0
        for entry in entries:
            matched_any = False
            for kw in entry["keywords"]:
                if kw in content:
                    kw_len = len(kw)
                    if kw_len > max_len:
                        max_len = kw_len
                    matched_any = True
            if matched_any:
                entry_count += 1
        if entry_count > 0 and (entry_count, max_len) > best_score:
            best_score = (entry_count, max_len)
            best = major
    return best


def classify(
    content: str,
    *,
    classifications: list[dict] | None = None,
    noise_exact: set[str] | None = None,
    noise_patterns: list[str] | None = None,
    compiled_noise: list[re.Pattern] | None = None,
) -> tuple[str | None, str | None]:
    """对维修内容进行大类+小类分类。

    两级层次匹配：
      1. 先按 (entry_count, max_keyword_len) 评分选出最佳大类；
      2. 再在大类内按原顺序（具体优先）匹配小类。
      entry_count = 命中关键词的小类数量，max_keyword_len = 最长匹配关键词字符数。

    Args:
        content: 维修内容文本。
        classifications: 分类规则列表，None 时使用默认值。
        noise_exact: 精确噪声集合，None 时使用默认值。
        noise_patterns: 正则噪声列表（字符串），None 时使用默认值。
            如果提供了 compiled_noise，则忽略此参数。
        compiled_noise: 预编译的噪声正则列表，优先于 noise_patterns 使用。

    Returns:
        (大类, 小类)，无实质内容时返回 (None, None)。
    """
    if classifications is None:
        classifications = _DEFAULT_CLASSIFICATIONS
    if noise_exact is None:
        noise_exact = _DEFAULT_NOISE_EXACT
    if compiled_noise is None:
        patterns = noise_patterns if noise_patterns is not None else _DEFAULT_NOISE_PATTERNS
        compiled_noise = compile_noise_patterns(patterns)

    if not content or content in noise_exact:
        return None, None
    for pat in compiled_noise:
        if pat.match(content.strip()):
            return None, None

    # 两级层次匹配：先确定大类，再在大类内匹配小类
    grouped = _group_by_major(classifications)
    best_major = _best_major(content, grouped)
    if best_major is None:
        return "其他", "未分类"

    for entry in grouped[best_major]:
        if any(kw in content for kw in entry["keywords"]):
            return best_major, entry["minor"]
    return best_major, "未分类"


def import_classifications_from_excel(path: str) -> dict:
    """从 Excel 配置模板导入分类规则。

    Sheet 结构：
    - "分类规则": 大类 | 小类 | 关键词（顿号分隔）
    - "噪声过滤": 类型（精确匹配/正则） | 值
    - "原因规则": 原因 | 处理方式（故障/检查内容/非故障/跳过）

    Args:
        path: Excel 文件路径。

    Returns:
        完整分类配置 dict，结构同 get_default_classifications()。

    Raises:
        ValueError: 文件格式错误或缺少必要 sheet。
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    # ── Sheet 1: 分类规则 ──
    if "分类规则" not in wb.sheetnames:
        wb.close()
        raise ValueError("Excel 文件缺少 '分类规则' sheet")

    classifications = []
    ws = wb["分类规则"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    for row in rows:
        if not row or not row[0]:
            continue
        major = str(row[0]).strip()
        minor = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        kw_raw = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        if not major or not minor:
            continue
        keywords = [k.strip() for k in kw_raw.split("、") if k.strip()]
        if keywords:
            classifications.append({"major": major, "minor": minor, "keywords": keywords})

    # ── Sheet 2: 噪声过滤 ──
    noise_exact: set[str] = set()
    noise_patterns: list[str] = []
    if "噪声过滤" in wb.sheetnames:
        ws = wb["噪声过滤"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            filter_type = str(row[0]).strip()
            value = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if not value:
                continue
            if filter_type == "精确匹配":
                noise_exact.add(value)
            elif filter_type == "正则":
                noise_patterns.append(value)

    # ── Sheet 3: 原因规则 ──
    reason_rules: dict[str, str] = {}
    _REASON_MAP = {"故障": "fault", "检查内容": "check_content", "非故障": "non_fault", "跳过": "skip"}
    if "原因规则" in wb.sheetnames:
        ws = wb["原因规则"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            reason = str(row[0]).strip()
            method = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            mapped = _REASON_MAP.get(method)
            if reason and mapped:
                reason_rules[reason] = mapped

    wb.close()

    # 空值兜底
    if not classifications:
        logger.warning("导入的分类规则为空，使用默认值")
        classifications = [dict(c) for c in _DEFAULT_CLASSIFICATIONS]
    if not noise_exact:
        noise_exact = set(_DEFAULT_NOISE_EXACT)
    if not noise_patterns:
        noise_patterns = list(_DEFAULT_NOISE_PATTERNS)
    if not reason_rules:
        reason_rules = dict(_DEFAULT_REASON_RULES)

    logger.info("从 Excel 导入分类配置: %d 条规则, %d 个精确噪声, %d 个正则噪声",
                len(classifications), len(noise_exact), len(noise_patterns))
    return {
        "classifications": classifications,
        "noise_exact": noise_exact,
        "noise_patterns": noise_patterns,
        "reason_rules": reason_rules,
    }


def export_classification_template(path: str, *, with_defaults: bool = False) -> str:
    """导出维修分类 Excel 配置模板。

    Args:
        path: 输出文件路径。
        with_defaults: True 时填充默认数据，False 时只输出表头和示例行。

    Returns:
        输出文件路径。
    """
    data = get_default_classifications() if with_defaults else None
    classifications = data["classifications"] if data else _DEFAULT_CLASSIFICATIONS[:3]
    noise_exact = data["noise_exact"] if data else {"出车", "已点检"}
    noise_patterns = data["noise_patterns"] if data else [r"^已?点检[，,/\s]*正常[。]?\s*$"]
    reason_rules = data["reason_rules"] if data else _DEFAULT_REASON_RULES

    wb = openpyxl.Workbook()

    # ── Sheet 1: 分类规则 ──
    ws1 = wb.active
    ws1.title = "分类规则"
    headers1 = ["大类", "小类", "关键词"]
    for col, h in enumerate(headers1, 1):
        _apply_header(ws1.cell(row=1, column=col, value=h))
    for row_idx, entry in enumerate(classifications, 2):
        _set_cell(ws1, row_idx, 1, entry["major"])
        _set_cell(ws1, row_idx, 2, entry["minor"])
        _set_cell(ws1, row_idx, 3, "、".join(entry["keywords"]))
        ws1.cell(row=row_idx, column=3).alignment = Alignment(wrap_text=True)
    ws1.column_dimensions["A"].width = 16
    ws1.column_dimensions["B"].width = 20
    ws1.column_dimensions["C"].width = 60
    ws1.freeze_panes = "A2"
    ws1.auto_filter.ref = f"A1:C{max(len(classifications), 1) + 1}"

    # ── Sheet 2: 噪声过滤 ──
    ws2 = wb.create_sheet("噪声过滤")
    headers2 = ["类型", "值"]
    for col, h in enumerate(headers2, 1):
        _apply_header(ws2.cell(row=1, column=col, value=h))
    row_idx = 2
    for val in sorted(noise_exact):
        _set_cell(ws2, row_idx, 1, "精确匹配")
        _set_cell(ws2, row_idx, 2, val)
        row_idx += 1
    for pat in noise_patterns:
        _set_cell(ws2, row_idx, 1, "正则")
        _set_cell(ws2, row_idx, 2, pat)
        row_idx += 1
    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 60
    ws2.freeze_panes = "A2"

    # ── Sheet 3: 原因规则 ──
    ws3 = wb.create_sheet("原因规则")
    headers3 = ["原因", "处理方式", "说明"]
    for col, h in enumerate(headers3, 1):
        _apply_header(ws3.cell(row=1, column=col, value=h))
    _REASON_DESC = {
        "fault": "故障", "check_content": "检查内容",
        "non_fault": "非故障", "skip": "跳过",
    }
    _REASON_EXPLAIN = {
        "fault": "视为故障记录", "check_content": "需检查维修内容是否为噪声",
        "non_fault": "不视为故障", "skip": "不进入明细",
    }
    for row_idx, (reason, method) in enumerate(reason_rules.items(), 2):
        _set_cell(ws3, row_idx, 1, reason)
        _set_cell(ws3, row_idx, 2, _REASON_DESC.get(method, method))
        _set_cell(ws3, row_idx, 3, _REASON_EXPLAIN.get(method, ""))
    ws3.column_dimensions["A"].width = 12
    ws3.column_dimensions["B"].width = 14
    ws3.column_dimensions["C"].width = 30
    ws3.freeze_panes = "A2"

    wb.save(path)
    logger.info("分类配置模板已导出: %s", path)
    return path
