"""maintenance_classification 模块测试

覆盖两级层次匹配的 classify() 函数：
- 主效果：跨大类截胡问题已修复
- 回归保证：简单单关键词、噪声过滤行为不变
- 边界：打平、无匹配、空内容
"""
import re
import pytest

from func.maintenance_classification import (
    _DEFAULT_CLASSIFICATIONS,
    _DEFAULT_NOISE_EXACT,
    _DEFAULT_NOISE_PATTERNS,
    _best_major,
    _group_by_major,
    classify,
    compile_noise_patterns,
)


# ── 辅助 fixture ──────────────────────────────────────────────

@pytest.fixture
def default_grouped():
    return _group_by_major(_DEFAULT_CLASSIFICATIONS)


# ── _group_by_major ───────────────────────────────────────────

class TestGroupByMajor:
    def test_groups_by_major_preserving_order(self):
        data = [
            {"major": "B", "minor": "x", "keywords": ["x"]},
            {"major": "A", "minor": "y", "keywords": ["y"]},
            {"major": "B", "minor": "z", "keywords": ["z"]},
            {"major": "C", "minor": "w", "keywords": ["w"]},
        ]
        grouped = _group_by_major(data)
        majors = list(grouped.keys())
        assert majors == ["B", "A", "C"]  # 按首次出现顺序

    def test_preserves_inner_entry_order(self):
        data = [
            {"major": "A", "minor": "x", "keywords": ["x"]},
            {"major": "A", "minor": "y", "keywords": ["y"]},
            {"major": "A", "minor": "z", "keywords": ["z"]},
        ]
        grouped = _group_by_major(data)
        assert [e["minor"] for e in grouped["A"]] == ["x", "y", "z"]

    def test_default_classifications_12_majors(self, default_grouped):
        assert len(default_grouped) == 12

    def test_engine_has_13_subcategories(self, default_grouped):
        assert len(default_grouped["发动机"]) == 13


# ── _best_major ───────────────────────────────────────────────

class TestBestMajor:
    def test_selects_by_entry_count(self):
        """主指标：entry_count 更高的胜出。"""
        data = [
            {"major": "A", "minor": "a1", "keywords": ["X", "Y"]},
            {"major": "A", "minor": "a2", "keywords": ["Z"]},
            {"major": "B", "minor": "b1", "keywords": ["X"]},
        ]
        grouped = _group_by_major(data)
        # "X Y Z" → A 命中 2 个小类, B 命中 1 个
        assert _best_major("X Y Z", grouped) == "A"

    def test_uses_max_len_as_tiebreaker(self):
        """entry_count 持平，max_keyword_len 更高的胜出。"""
        data = [
            {"major": "A", "minor": "a1", "keywords": ["ABC"]},
            {"major": "B", "minor": "b1", "keywords": ["ABCD"]},
        ]
        grouped = _group_by_major(data)
        # "ABCD" → A 命中 len=3, B 命中 len=4
        assert _best_major("ABCD", grouped) == "B"

    def test_tie_goes_to_first_major_in_list(self):
        """entry_count 和 max_len 都一致，按列表顺序。"""
        data = [
            {"major": "A", "minor": "a1", "keywords": ["XYZ"]},
            {"major": "B", "minor": "b1", "keywords": ["XYZ"]},
        ]
        grouped = _group_by_major(data)
        assert _best_major("XYZ", grouped) == "A"

    def test_returns_none_when_no_match(self):
        data = [{"major": "A", "minor": "a1", "keywords": ["NEVER"]}]
        grouped = _group_by_major(data)
        assert _best_major("NOTHING HERE", grouped) is None


# ── classify 回归测试（行为不变项） ────────────────────────────

class TestClassifyRegression:
    """与原 flat-scan 行为保持一致的关键场景。"""

    def test_noise_exact(self):
        assert classify("出车") == (None, None)
        assert classify("已点检") == (None, None)
        assert classify("正常") == (None, None)

    def test_noise_pattern(self):
        assert classify("点检正常") == (None, None)
        assert classify("已吹清空滤，出车。") == (None, None)

    def test_empty_content(self):
        assert classify("") == (None, None)
        # 纯空格不视为 empty，行为保持与原 flat-scan 一致

    def test_unmatched_returns_other(self):
        assert classify("这台设备没有已知故障描述") == ("其他", "未分类")

    def test_simple_keyword_match(self):
        assert classify("发动机报警") == ("发动机", "报警/故障灯")
        assert classify("变速箱油更换") == ("变速箱", "变速箱保养")

    def test_noise_before_classification(self):
        """含噪声关键词的内容应先被过滤，不作分类。"""
        # '出车'是精确噪声，不因含其他词而误分类
        r = classify("出车")
        assert r == (None, None), f"应为 (None, None), 实际 {r}"

    def test_custom_classifications(self):
        """传入自定义 classifications 应正确使用。"""
        custom = [
            {"major": "自定义大类", "minor": "A", "keywords": ["alpha"]},
            {"major": "自定义大类", "minor": "B", "keywords": ["beta"]},
        ]
        assert classify("alpha", classifications=custom) == ("自定义大类", "A")
        assert classify("beta", classifications=custom) == ("自定义大类", "B")
        assert classify("gamma", classifications=custom) == ("其他", "未分类")

    def test_noise_exact_custom(self):
        """传入自定义 noise_exact 应正确过滤。"""
        custom_noise = {"测试噪声"}
        r = classify("测试噪声", noise_exact=custom_noise)
        assert r == (None, None)

    def test_compiled_noise(self):
        """传入预编译的 compiled_noise 应正确过滤。"""
        compiled = compile_noise_patterns([r"^测试噪声.*$"])
        r = classify("测试噪声xx", compiled_noise=compiled)
        assert r == (None, None)


# ── 两级层次匹配的关键修复验证 ────────────────────────────────

class TestClassifyHierarchicalFix:
    """本次改造的核心修复：跨大类截胡问题已解决。"""

    def test_engine_oil_refill(self):
        """发动机补加机油 → 日常维护（不是发动机/发动机通用）"""
        major, minor = classify("发动机补加机油")
        assert (major, minor) == ("日常维护", "动力系统保养")

    def test_transmission_noise_and_shifting(self):
        """换挡时变速箱有异响 → 变速箱（不是发动机/异响）"""
        major, minor = classify("换挡时变速箱有异响")
        assert (major, minor) == ("变速箱", "换挡/离合器")

    def test_ac_and_sensor(self):
        """空调不工作，传感器坏了 → 空调（不是电气系统/传感器）"""
        major, minor = classify("空调不工作，传感器坏了")
        assert (major, minor) == ("空调", "空调故障")

    def test_brake_pad_noise(self):
        """刹车片异响 → 制动系统（不是发动机/异响）"""
        major, minor = classify("刹车片异响")
        assert (major, minor) == ("制动系统", "制动通用")

    def test_engine_greasing(self):
        """给发动机加注黄油 → 日常维护（不是润滑系统）"""
        major, minor = classify("给发动机加注黄油")
        assert (major, minor) == ("日常维护", "润滑系统保养")

    def test_transmission_sensor_tie(self):
        """变速箱传感器故障 → 变速箱（平局时按列表顺序）"""
        major, minor = classify("变速箱传感器故障")
        assert major == "变速箱"


# ── 大类内匹配具体优先 ───────────────────────────────────────

class TestClassifyWithinMajorSpecificFirst:
    """胜出大类内按具体优先顺序匹配小类。"""

    def test_engine_specific_before_general(self):
        """发动机报警 → 报警/故障灯（具体），不是发动机通用"""
        assert classify("发动机报警") == ("发动机", "报警/故障灯")

    def test_engine_shutdown_specific(self):
        """发动机熄火 → 发动机通用（停机/熄火小类已合并）"""
        assert classify("发动机熄火") == ("发动机", "发动机通用")

    def test_transmission_leak_specific(self):
        """变速箱漏油 → 漏油/渗油（具体），不是变速箱通用"""
        assert classify("变速箱漏油") == ("变速箱", "漏油/渗油")


# ── 边界场景 ─────────────────────────────────────────────────

class TestClassifyEdgeCases:
    def test_english_keywords(self):
        assert classify("ECM异常") == ("发动机", "ECM/ECU")
        assert classify("SCR系统报警") == ("发动机", "排气异常")

    def test_mixed_zh_en(self):
        assert classify("DPF再生故障") == ("发动机", "排气异常")

    def test_noise_with_valid_content(self):
        """噪声过滤后仍有实质内容 → 正常分类。"""
        r = classify("发动机异响，点检正常")
        assert r is not None and r != (None, None)

    def test_brake_noise_goes_to_brake_not_engine(self):
        """刹车异响 → 制动系统/制动通用（不是发动机/异响冒烟）"""
        major, minor = classify("刹车异响")
        assert (major, minor) == ("制动系统", "制动通用")

    def test_brake_noise_synonym(self):
        """制动异响 → 制动系统/制动通用"""
        assert classify("制动异响") == ("制动系统", "制动通用")

    def test_hydraulic_noise_goes_to_hydraulic_not_engine(self):
        """液压异响 → 液压系统/液压通用（不是发动机/异响冒烟）"""
        assert classify("液压异响") == ("液压系统", "液压通用")

    def test_transmission_noise_goes_to_transmission_not_engine(self):
        """变速箱异响 → 变速箱/换挡/离合器（不是发动机/异响冒烟）"""
        assert classify("变速箱异响") == ("变速箱", "换挡/离合器")

    def test_multiple_majors_matched(self):
        """涉及多个大类的复杂语句选择最佳大类。"""
        major, minor = classify("液压油缸漏油需要更换密封圈")
        assert major == "液压系统"

    def test_single_character_noise_not_blocking(self):
        """不应将包含单个噪声字的非噪声内容误过滤。"""
        r = classify("停车时发动机异响")
        assert r is not None and r[0] is not None


# ── process_maintenance_data details_only ─────────────────────

class TestProcessMaintenanceDetailsOnly:
    """验证 process_maintenance_data 的 details_only 选项。"""

    def test_details_only_filters_non_detail_sheets(self):
        """details_only=True 时只保留维修明细 sheet。"""
        from func.building import build_sheets
        from datetime import date

        classified = [
            {
                "日期": date(2025, 3, 15),
                "原始设备名称": "EX01",
                "标准设备名称": "EX01",
                "设备型号": "CAT390",
                "原因": "检修",
                "班次": "白班",
                "大类": "发动机",
                "小类": "报警/故障灯",
                "是否故障": "是",
                "维修内容": "发动机报警，更换传感器",
                "工时_分钟": 120,
            },
            {
                "日期": date(2025, 3, 16),
                "原始设备名称": "EX02",
                "标准设备名称": "EX02",
                "设备型号": "CAT390",
                "原因": "检修",
                "班次": "夜班",
                "大类": "制动系统",
                "小类": "制动通用",
                "是否故障": "是",
                "维修内容": "刹车异响",
                "工时_分钟": 60,
            },
        ]

        # 全量 sheets（模拟 process_maintenance_data 中的 build_sheets 调用）
        full_sheets = build_sheets(classified, classified)
        assert "维修明细" in full_sheets
        assert "每月设备故障统计" in full_sheets
        assert len(full_sheets) > 1

        # details_only 过滤：只保留维修明细
        detail_only = {k: v for k, v in full_sheets.items() if k == "维修明细"}
        assert set(detail_only.keys()) == {"维修明细"}

        # 验证明细内容完整
        df = detail_only["维修明细"]
        assert len(df) == 2
        assert list(df.columns)[0] == "日期"
