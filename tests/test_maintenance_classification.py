"""维修记录分类引擎测试。"""
from pathlib import Path

import pytest

from func.maintenance_classification import (
    _DEFAULT_CLASSIFICATIONS,
    _best_major,
    _group_by_major,
    classify,
    compile_noise_patterns,
    export_classification_template,
    import_classifications_from_excel,
    is_fault_record,
    normalize_maintenance_content,
)


@pytest.fixture
def default_grouped():
    return _group_by_major(_DEFAULT_CLASSIFICATIONS)


class TestRuleStructure:
    def test_groups_preserve_order(self):
        data = [
            {"major": "B", "minor": "x", "keywords": ["x"]},
            {"major": "A", "minor": "y", "keywords": ["y"]},
            {"major": "B", "minor": "z", "keywords": ["z"]},
        ]
        grouped = _group_by_major(data)
        assert list(grouped) == ["B", "A"]
        assert [entry["minor"] for entry in grouped["B"]] == ["x", "z"]

    def test_default_taxonomy_has_19_rule_majors_plus_other_fallback(
        self, default_grouped
    ):
        assert len(default_grouped) == 19
        assert len(_DEFAULT_CLASSIFICATIONS) == 99

    def test_best_major_compatibility_helper(self):
        data = [
            {"major": "A", "minor": "a1", "keywords": ["X", "Y"]},
            {"major": "A", "minor": "a2", "keywords": ["Z"]},
            {"major": "B", "minor": "b1", "keywords": ["X"]},
        ]
        assert _best_major("X Y Z", _group_by_major(data)) == "A"


class TestNormalizationAndNoise:
    def test_casefold_and_metadata_cleanup(self):
        normalized = normalize_maintenance_content(
            "Author: A; 发动机小时数: 12345; IGBT 报警"
        )
        assert normalized == "igbt 报警"

    def test_empty_or_noise_content(self):
        assert classify("") == (None, None)
        assert classify("已点检") == (None, None)
        assert classify("点检正常") == (None, None)
        assert classify("发动机小时数：12345") == (None, None)

    def test_noise_with_fault_content_is_not_discarded(self):
        assert classify("发动机异响，点检正常") == (
            "发动机系统",
            "性能/工况异常",
        )

    def test_custom_noise_regex(self):
        compiled = compile_noise_patterns([r"^测试噪声.*$"])
        assert classify("测试噪声xx", compiled_noise=compiled) == (None, None)


class TestConfirmedTaxonomy:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("主发电机励磁故障", ("电驱动系统", "主发电机")),
            ("左后轮马达报警", ("电驱动系统", "轮马达/电动轮")),
            ("IGBT功率模块损坏", ("电驱动系统", "逆变/功率模块")),
            ("举升缸漏油", ("液压系统", "举升/工作装置油缸")),
            ("转向油缸渗油", ("液压系统", "转向油缸")),
            ("右前悬挂缸漏油", ("液压系统", "悬挂油缸")),
        ],
    )
    def test_user_confirmed_boundaries(self, content, expected):
        assert classify(content) == expected

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("轮马达电气报警", ("电驱动系统", "轮马达/电动轮")),
            ("主发电机电气故障", ("电驱动系统", "主发电机")),
            ("IGBT控制模块报警", ("电驱动系统", "逆变/功率模块")),
            ("举升缸不工作", ("液压系统", "举升/工作装置油缸")),
            ("转向缸液压油漏", ("液压系统", "转向油缸")),
            ("悬挂缸报警", ("液压系统", "悬挂油缸")),
        ],
    )
    def test_confirmed_boundaries_win_over_generic_terms(self, content, expected):
        assert classify(content) == expected

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("差速器异响", ("传动与车桥", "车桥/差速器/半轴")),
            ("变速箱漏油", ("变速箱与变矩器", "油路/滤清/冷却")),
            ("SCR系统报警", ("发动机系统", "排气与尾气后处理")),
            ("DPF再生故障", ("发动机系统", "排气与尾气后处理")),
            ("ECM异常报码", ("低压电气与控制", "控制器/模块/故障码")),
            ("液压油缸漏油需要更换密封圈", ("液压系统", "通用液压油缸")),
        ],
    )
    def test_specific_system_matches(self, content, expected):
        assert classify(content) == expected

    def test_generic_cab_noise_does_not_become_engine(self):
        assert classify("驾驶室异响") == ("其他/待确认", "仅现象未定位")

    def test_unmatched_uses_single_fallback(self):
        assert classify("这台设备没有已知故障描述") == (
            "其他/待确认",
            "仅现象未定位",
        )


class TestPlannedMaintenance:
    @pytest.mark.parametrize(
        ("content", "minor"),
        [
            ("完成500小时保养", "周期保养"),
            ("吹清空滤后出车", "滤芯保养"),
            ("补加防冻液20升", "油液补加/更换"),
            ("轮胎换位", "轮胎充气/换位"),
        ],
    )
    def test_plan_is_classified_for_details(self, content, minor):
        assert classify(content) == ("计划保养与非故障作业", minor)

    def test_plan_is_not_fault(self):
        assert not is_fault_record("检修", "完成500小时保养")
        assert not is_fault_record("保养", "更换机油")

    def test_fault_marker_prevents_plan_rule_from_hiding_fault(self):
        major, _ = classify("补加防冻液时发现水箱漏水")
        assert major != "计划保养与非故障作业"

    def test_normal_inspection_is_not_fault(self):
        assert not is_fault_record("检修", "点检正常")
        assert not is_fault_record("点检", "检查均为正常")

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("已充黄油，出车", ("计划保养与非故障作业", "润滑/补脂")),
            ("补加液压油200升", ("计划保养与非故障作业", "油液补加/更换")),
            (
                "500小时保养时发现转向泵油管漏油并更换",
                ("转向系统", "转向泵/阀"),
            ),
            (
                "液压管破裂，补加液压油200升",
                ("液压系统", "管路/接头/密封"),
            ),
        ],
    )
    def test_pure_maintenance_and_fault_boundary(self, content, expected):
        assert classify(content) == expected


class TestEngineElectricalBoundary:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("发动机打不着", ("其他/待确认", "仅现象未定位")),
            (
                "发动机打不着，更换启动机",
                ("低压电气与控制", "启动机/启动回路"),
            ),
            (
                "发动机无法启动，检查飞轮齿圈损坏",
                ("发动机系统", "启动机械/飞轮"),
            ),
            (
                "发动机报警，ECM报码",
                ("低压电气与控制", "控制器/模块/故障码"),
            ),
            (
                "发动机没劲，第3喷油器故障",
                ("发动机系统", "燃油供给与喷射"),
            ),
        ],
    )
    def test_root_cause_component_owns_starting_fault(self, content, expected):
        assert classify(content) == expected


class TestStructureOwnershipBoundary:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("空调没有皮带", ("空调与暖风", "制冷回路")),
            ("制动底座损坏", ("制动系统", "行车制动")),
            ("主发轴承异响", ("电驱动系统", "主发电机")),
            ("悬挂轴承裂了", ("悬挂与车架", "减震/弹簧/悬挂通用")),
            ("铲斗销断裂", ("工作装置", "销轴/衬套")),
            ("支架断裂", ("结构件与通用机械", "支架/底座/护架")),
        ],
    )
    def test_specific_system_owns_generic_part(self, content, expected):
        assert classify(content) == expected


class TestAdvancedExcelRuleSchema:
    def test_export_import_round_trip(self, tmp_path: Path):
        path = tmp_path / "rules.xlsx"
        export_classification_template(str(path), with_defaults=True)
        rules = import_classifications_from_excel(str(path))
        assert rules["classifications"]
        assert any(
            entry.get("exclude_keywords")
            for entry in rules["classifications"]
        )
        assert any(
            entry.get("regex_keywords")
            for entry in rules["classifications"]
        )

    def test_custom_combination_and_exclusion(self):
        custom = [
            {
                "major": "A",
                "minor": "组合",
                "keywords": [],
                "all_keywords": [["液压", "报警"]],
                "exclude_keywords": ["正常"],
            }
        ]
        assert classify("液压系统报警", classifications=custom) == ("A", "组合")
        assert classify("液压报警后检查正常", classifications=custom) == (
            "其他/待确认",
            "仅现象未定位",
        )

    def test_equal_cross_system_scores_go_to_single_review_category(self):
        custom = [
            {"major": "A", "minor": "A1", "keywords": ["同词"]},
            {"major": "B", "minor": "B1", "keywords": ["同词"]},
        ]
        assert classify("同词", classifications=custom) == (
            "其他/待确认",
            "多系统/需拆分",
        )


class TestMaintenanceDetails:
    def test_planned_maintenance_keeps_category_but_not_fault(
        self, monkeypatch, tmp_path: Path
    ):
        from datetime import date
        from func import excel_maintenance

        source = tmp_path / "input.xlsx"
        source.touch()
        records = [
            {
                "日期": date(2026, 7, 1),
                "原始设备名称": "TR001",
                "原因": "保养",
                "班次": "白班",
                "维修内容": "完成500小时保养",
                "工时_分钟": 120,
            }
        ]
        monkeypatch.setattr(
            excel_maintenance,
            "extract_all_records",
            lambda *args, **kwargs: records,
        )

        sheets = excel_maintenance.process_maintenance_data(
            str(source),
            return_sheets=True,
            details_only=True,
        )
        row = sheets["维修明细"].iloc[0]
        assert row["大类"] == "计划保养与非故障作业"
        assert row["小类"] == "周期保养"
        assert row["是否故障"] == "否"
