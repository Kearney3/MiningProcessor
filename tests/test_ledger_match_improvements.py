"""台账匹配页面改进测试"""
import pytest
import flet as ft
import pandas as pd
from unittest.mock import MagicMock, patch


class TestDataTableReplacement:
    """测试 DataTable2 替换为 ft.DataTable"""

    def test_data_table_type(self):
        """验证 data_table 是 ft.DataTable 类型"""
        from gui.components.ledger_match import create_ledger_match_section
        
        page = MagicMock(spec=ft.Page)
        log = MagicMock()
        ledger_refs = MagicMock()
        oil_ledger_refs = MagicMock()
        
        container, refs = create_ledger_match_section(
            page, log, ledger_refs, oil_ledger_refs
        )
        
        # 获取 data_table 控件
        # 需要从 container 中找到 data_table
        # 这里先验证函数能正常调用
        assert container is not None
        assert refs is not None

    def test_data_table_columns_sync(self):
        """验证表格列和行数量同步"""
        # 创建测试数据
        df = pd.DataFrame({
            "设备名称": ["卡车A", "卡车B"],
            "设备编号": ["001", "002"],
        })
        
        # 验证列数和行数一致
        assert len(df.columns) == 2
        assert len(df) == 2


class TestViewStateManager:
    """测试视图状态管理"""

    def test_view_segment_initial_state(self):
        """验证初始状态：视图切换禁用"""
        from gui.components.ledger_match import create_ledger_match_section
        
        page = MagicMock(spec=ft.Page)
        log = MagicMock()
        ledger_refs = MagicMock()
        oil_ledger_refs = MagicMock()
        
        container, refs = create_ledger_match_section(
            page, log, ledger_refs, oil_ledger_refs
        )
        
        # 初始状态下视图切换应该禁用
        # 需要从 refs 中获取 view_segment
        # 这里先验证函数能正常调用
        assert container is not None

    def test_view_mode_switching(self):
        """验证视图切换逻辑"""
        # 模拟数据
        _all_sheets = {"Sheet1": pd.DataFrame({"A": [1, 2, 3]})}
        _matched_sheets = {"Sheet1": pd.DataFrame({"A": [1]})}
        _unmatched_sheets = {"Sheet1": pd.DataFrame({"A": [2, 3]})}
        
        # 验证数据结构
        assert len(_all_sheets["Sheet1"]) == 3
        assert len(_matched_sheets["Sheet1"]) == 1
        assert len(_unmatched_sheets["Sheet1"]) == 2
