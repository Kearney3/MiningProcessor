"""用户自定义配置区域组件（优化后的表单布局与错误处理）"""
from __future__ import annotations

import logging

import flet as ft

from gui.components.types import UserConfigRefs

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from gui.components.common import _log_message

from ._keywords import _create_keywords_section
from ._header_mapping import _create_header_mapping_section
from ._minebase import _create_minebase_section
from ._column_mapping import _create_column_mapping_section
from ._anomaly import _create_anomaly_config_section
from ._llm import _create_llm_config_section
from ._daily_report import _create_daily_report_config_section

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
    daily_report_card, daily_report_refs = _create_daily_report_config_section(page, log)

    def _reload_all():
        """重新加载所有子区域的配置。"""
        llm_refs["reload"]()
        kw_refs["reload"]()
        hm_refs["reload"]()
        mb_refs["reload"]()
        map_refs["reload"]()
        map_refs["build"]()
        anomaly_refs["reload"]()
        daily_report_refs["reload"]()

    def _on_reset_all(e):
        """还原所有用户配置为默认值。"""

        def _do_reset(e_confirm):
            page.pop_dialog()
            config_loader.reset_all_user_overrides()
            _reload_all()
            _log_message(log, "已还原所有用户配置为默认值")
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass

        def _on_cancel(e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认还原"),
            content=ft.Text("将清除所有用户自定义配置，恢复为系统默认值。\n此操作不可撤销，是否继续？"),
            actions=[
                ft.TextButton("确认还原", on_click=_do_reset),
                ft.TextButton("取消", on_click=_on_cancel),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    reset_all_btn = theme.secondary_btn(
        "还原为默认配置",
        icon=ft.Icons.RESTART_ALT,
        on_click=_on_reset_all,
    )

    container = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [theme.section_title("用户配置"), reset_all_btn],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                section_hint,
                llm_card,
                minebase_card,
                keywords_card,
                header_mapping_card,
                mapping_card,
                anomaly_card,
                daily_report_card,
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

    _reload_all()
    return container, refs
