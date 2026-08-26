"""系统资源配置区域组件。"""
from __future__ import annotations

import contextlib
import logging

import flet as ft

try:
    from gui import theme
except ImportError:
    import gui.theme as theme

from func import config_loader
from gui.components.common import _log_message
from gui.i18n import t


def _create_system_resource_section(page: ft.Page, log):
    """创建系统资源设置卡片，返回 (card, refs_dict)。"""

    cpu_cores = ft.TextField(
        label=t("components:user_config._system.cpuCores"),
        width=180,
        dense=True,
        text_size=13,
        input_filter=ft.InputFilter(allow=True, regex_string=r"^[0-9]*$"),
        color=theme.TEXT_PRIMARY,
        border_color=theme.BORDER,
        focused_border_color=theme.PRIMARY,
    )
    available_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    status_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)

    def _set_status(message: str, color=theme.TEXT_SECONDARY):
        status_text.value = message
        status_text.color = color

    def _reload(_e=None):
        available = config_loader.get_available_cpu_cores()
        cpu_cores.value = str(config_loader.get_cpu_cores())
        cpu_cores.error_text = None
        available_text.value = t(
            "components:user_config._system.availableCpuCores",
            available=available,
        )
        _set_status("")
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _save(_e=None):
        try:
            value = config_loader.validate_cpu_cores(cpu_cores.value)
        except ValueError:
            available = config_loader.get_available_cpu_cores()
            cpu_cores.error_text = t(
                "components:user_config._system.invalidCpuCores",
                available=available,
            )
            _set_status(cpu_cores.error_text, theme.ERROR)
            _log_message(log, cpu_cores.error_text, level=logging.WARNING)
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()
            return

        try:
            config_loader.set_cpu_cores(value)
        except ValueError as exc:
            cpu_cores.error_text = str(exc)
            _set_status(str(exc), theme.ERROR)
            _log_message(log, str(exc), level=logging.WARNING)
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()
            return

        cpu_cores.error_text = None
        _set_status(t("components:user_config._system.cpuCoresSaved"), theme.SUCCESS)
        _log_message(log, t("components:user_config._system.savedCpuCores", count=value))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _reset(_e=None):
        config_loader.reset_user_config(config_loader.CPU_CORES_CONFIG_KEY)
        _reload()
        _set_status(t("components:user_config._system.defaultConfigurationRestored"))
        _log_message(log, t("components:user_config._system.defaultConfigurationRestored"))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    action_buttons = [
        theme.primary_btn(
            t("components:user_config._system.save"),
            icon=ft.Icons.SAVE,
            on_click=_save,
        ),
        theme.secondary_btn(
            t("components:user_config._system.reload"),
            icon=ft.Icons.REFRESH,
            on_click=_reload,
        ),
        theme.secondary_btn(
            t("components:user_config._system.restoreDefault"),
            icon=ft.Icons.RESTART_ALT,
            on_click=_reset,
        ),
    ]

    card = theme.make_collapsible(
        title=t("components:user_config._system.systemResourceSettings"),
        subtitle=t("components:user_config._system.configureCpuResourcesForDataProcessing"),
        icon=getattr(ft.Icons, "MEMORY", ft.Icons.SETTINGS),
        initially_expanded=False,
        content_controls=[
            ft.Text(
                t("components:user_config._system.cpuCoresHint"),
                size=12,
                color=theme.TEXT_SECONDARY,
            ),
            ft.Row(
                [cpu_cores, available_text],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(action_buttons, spacing=8, wrap=True),
            status_text,
        ],
    )

    _reload()
    return card, {
        "cpu_cores": cpu_cores,
        "available_cpu_cores": available_text,
        "status_text": status_text,
        "action_buttons": action_buttons,
        "reload": _reload,
        "save": _save,
        "reset": _reset,
    }

