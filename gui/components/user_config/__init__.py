"""用户自定义配置区域组件（优化后的表单布局与错误处理）"""
from __future__ import annotations

import flet as ft

from gui.components.types import UserConfigRefs

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from ._keywords import _create_keywords_section
from ._header_mapping import _create_header_mapping_section
from ._minebase import _create_minebase_section
from ._column_mapping import _create_column_mapping_section
from ._anomaly import _create_anomaly_config_section
from ._llm import _create_llm_config_section

__all__ = ["create_user_config_section", "UserConfigRefs"]


def create_user_config_section(page: ft.Page, log) -> tuple[ft.Container, "UserConfigRefs"]:
    """创建用户配置页面，返回 (container, refs)。"""

    section_hint = ft.Text(
        "这里用于管理与业务处理无关的个人偏好设置。",
        size=13,
        color=theme.TEXT_SECONDARY,
    )

    keywords_card, kw_refs = _create_keywords_section(page, log)
    header_mapping_card, hm_refs = _create_header_mapping_section(page, log)
    minebase_card, mb_refs = _create_minebase_section(page, log)
    mapping_card, map_refs = _create_column_mapping_section(page, log)
    anomaly_card, anomaly_refs = _create_anomaly_config_section(page, log)
    llm_card, llm_refs = _create_llm_config_section(page, log)

    container = ft.Container(
        content=ft.Column(
            [
                theme.section_title("用户配置"),
                section_hint,
                llm_card,
                minebase_card,
                keywords_card,
                header_mapping_card,
                mapping_card,
                anomaly_card,
            ],
            spacing=8,
            expand=True,
        ),
        padding=12,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS_LG,
        bgcolor=theme.SURFACE,
        expand=True,
    )

    refs: UserConfigRefs = {
        "mb_mode": mb_refs["mb_mode"],
        "mb_api_url": mb_refs["mb_api_url"],
        "mb_api_user": mb_refs["mb_api_user"],
        "mb_api_pass": mb_refs["mb_api_pass"],
        "mb_db_host": mb_refs["mb_db_host"],
        "mb_db_port": mb_refs["mb_db_port"],
        "mb_db_name": mb_refs["mb_db_name"],
        "mb_db_user": mb_refs["mb_db_user"],
        "mb_db_pass": mb_refs["mb_db_pass"],
        "mb_status_text": mb_refs["mb_status_text"],
        "mb_action_buttons": mb_refs["mb_action_buttons"],
        "mb_api_test_btn": mb_refs["mb_api_test_btn"],
        "mb_api_test_result": mb_refs["mb_api_test_result"],
        "mb_test_btn": mb_refs["mb_test_btn"],
        "mb_test_result": mb_refs["mb_test_result"],
        "reload_mb_config": mb_refs["reload"],
        "save_mb_config": mb_refs["save"],
        "reset_mb_config": mb_refs["reset"],
        "reload_keywords": kw_refs["reload"],
        "reload_header_mapping": hm_refs["reload"],
        "reload_llm_config": llm_refs["reload"],
    }

    llm_refs["reload"]()
    kw_refs["reload"]()
    hm_refs["reload"]()
    mb_refs["reload"]()
    map_refs["reload"]()
    map_refs["build"]()
    anomaly_refs["reload"]()
    return container, refs
