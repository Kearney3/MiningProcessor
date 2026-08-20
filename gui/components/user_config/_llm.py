"""LLM 标注配置区域组件。"""
import asyncio
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


def _create_llm_config_section(page: ft.Page, log):
    """创建 LLM 标注配置卡片，返回 (card, refs_dict)。"""

    llm_url = ft.TextField(label=t("components:user_config._llm.apiUrl"), hint_text="https://api.example.com/v1", expand=True, color=theme.TEXT_PRIMARY)
    llm_api_key = ft.TextField(label=t("common:apiKey"), password=True, can_reveal_password=True, expand=True, color=theme.TEXT_PRIMARY)
    llm_model = ft.Dropdown(label=t("components:user_config._llm.model"), expand=True, options=[], hint_text=t("components:user_config._llm.columnColumnmodelColumn"), editable=True)
    llm_format = ft.Dropdown(
        label=t("components:user_config._llm.apiFormat"),
        width=160,
        options=[
            ft.dropdown.Option("openai", t("components:user_config._llm.openaiCompatible")),
            ft.dropdown.Option("anthropic", t("common:anthropic")),
        ],
        value="openai",
    )
    llm_status = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    llm_test_result = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
    llm_verify_result = ft.Text("", size=12)
    from func.secret_store import LLM_KEY_MASK as _LLM_KEY_MASKED
    _llm_key_saved = False

    def _on_api_key_change(_e):
        nonlocal _llm_key_saved
        if llm_api_key.value != _LLM_KEY_MASKED:
            _llm_key_saved = False

    llm_api_key.on_change = _on_api_key_change

    def _apply_llm_to_ui(cfg: dict):
        nonlocal _llm_key_saved
        llm_url.value = cfg.get("url", "")
        raw_key = cfg.get("api_key", "")
        if raw_key:
            llm_api_key.value = _LLM_KEY_MASKED
            _llm_key_saved = True
        else:
            llm_api_key.value = ""
            _llm_key_saved = False
        llm_model.value = cfg.get("model", "") or None
        llm_format.value = cfg.get("format", "openai")
        llm_status.value = ""
        llm_test_result.value = ""

    def _reload_llm():
        cfg = config_loader.get_llm_config()
        _apply_llm_to_ui(cfg)
        if cfg.get("model") and not any(o.key == cfg["model"] for o in llm_model.options):
            llm_model.options.append(ft.dropdown.Option(cfg["model"]))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _resolve_api_key() -> str:
        val = (llm_api_key.value or "").strip()
        if _llm_key_saved and val == _LLM_KEY_MASKED:
            return ""  # 后端从持久化配置加载真实密钥
        return val

    def _fetch_models(_e):
        cfg = {
            "url": (llm_url.value or "").strip(),
            "api_key": _resolve_api_key(),
            "format": llm_format.value or "openai",
        }
        if not cfg["url"]:
            llm_test_result.value = t("components:user_config._llm.enterTheApiUrlFirstVariant")
            llm_test_result.color = ft.Colors.RED
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()
            return
        llm_test_result.value = t("components:user_config.fetchingModelList")
        llm_test_result.color = theme.TEXT_SECONDARY
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

        async def _do_fetch_async():
            result = await asyncio.to_thread(config_loader.test_llm_connection, cfg)
            if result["success"]:
                models = result["models"]
                llm_model.options = [ft.dropdown.Option(m) for m in models]
                if models and not llm_model.value:
                    llm_model.value = models[0]
                info = result.get("error", "")
                if models:
                    llm_test_result.value = t("components:user_config._llm.retrievedModels", count=len(models))
                    llm_test_result.color = theme.TEXT_PRIMARY
                    _log_message(log, t("components:user_config._llm.itemItemsitemmodel", count=len(models)))
                else:
                    llm_test_result.value = info or t("components:user_config._llm.noModelsReturnedEnterAModelNameManually")
                    llm_test_result.color = ft.Colors.ORANGE
                    _log_message(log, info or t("components:user_config._llm.theApiReturnedNoModelListEnterAModelNameManually"))
            else:
                llm_test_result.value = t("components:user_config._llm.connectionFailedVariant", error=result['error'])
                llm_test_result.color = ft.Colors.RED
                _log_message(log, t("components:user_config._llm.llmApiconnectionFailed", error=result['error']), level=logging.ERROR)
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()

        page.run_task(_do_fetch_async)

    def _save_llm(_e):
        api_key_val = llm_api_key.value or ""
        if _llm_key_saved and api_key_val == _LLM_KEY_MASKED:
            api_key_val = ""  # 未修改，后端跳过加密保留已有凭据
        updates = {
            "url": (llm_url.value or "").strip(),
            "api_key": api_key_val.strip(),
            "model": llm_model.value or "",
            "format": llm_format.value or "openai",
        }
        config_loader.update_llm_config(updates)
        # 重新加载以同步掩码状态
        _reload_llm()
        llm_status.value = t("components:user_config._llm.llmConfigurationSaved")
        _log_message(log, t("components:user_config._llm.savedLlmConfigurationconfiguration"))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    def _reset_llm(_e):
        config_loader.update_user_config({"llm_labeling": {}})
        _reload_llm()
        llm_status.value = t("components:user_config._llm.defaultConfigurationRestored")
        _log_message(log, t("components:user_config._llm.configurationLlmConfigurationconfiguration"))
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

    fetch_btn = theme.secondary_btn(t("components:user_config._llm.getModels"), icon=ft.Icons.REFRESH, on_click=_fetch_models)

    def _verify_connection(_e):
        cfg = {
            "url": (llm_url.value or "").strip(),
            "api_key": _resolve_api_key(),
            "format": llm_format.value or "openai",
        }
        if not cfg["url"]:
            llm_verify_result.value = t("components:user_config._llm.enterTheApiUrlFirstEnterApiUrlFirst")
            llm_verify_result.color = ft.Colors.AMBER
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()
            return
        llm_verify_result.value = t("components:user_config.verifying")
        llm_verify_result.color = theme.TEXT_SECONDARY
        with contextlib.suppress(RuntimeError, AttributeError):
            page.update()

        async def _do_verify_async():
            result = await asyncio.to_thread(config_loader.test_llm_connection, cfg)
            selected_model = (llm_model.value or "").strip()

            if result["success"]:
                models = result["models"]
                if selected_model and selected_model not in models:
                    llm_verify_result.value = t("components:user_config._llm.connectionSucceededConnectionmodel", selected_model=selected_model, count=len(models))
                    llm_verify_result.color = ft.Colors.AMBER
                else:
                    model_info = t("components:user_config._llm.modelItem", selected_model=selected_model) if selected_model else ""
                    llm_verify_result.value = t("components:user_config._llm.connectionSucceededItemsmodelconnection", count=len(models), model_info=model_info)
                    llm_verify_result.color = ft.Colors.GREEN
            else:
                llm_verify_result.value = t("components:user_config._llm.connectionFailedConnectionFailed", error=result['error'])
                llm_verify_result.color = ft.Colors.RED
            with contextlib.suppress(RuntimeError, AttributeError):
                page.update()

        page.run_task(_do_verify_async)

    verify_btn = theme.secondary_btn(t("components:user_config._llm.verifyConnection"), icon=ft.Icons.CHECK_CIRCLE, on_click=_verify_connection)
    action_buttons = [
        theme.primary_btn(t("components:user_config._llm.saveConfig"), icon=ft.Icons.SAVE, on_click=_save_llm),
        theme.secondary_btn(t("components:user_config._llm.reload"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_llm()),
        theme.secondary_btn(t("components:user_config._llm.restoreDefault"), icon=ft.Icons.RESTART_ALT, on_click=_reset_llm),
    ]

    llm_card = theme.make_collapsible(
        title=t("components:user_config._llm.llmConfigurationconfiguration"),
        subtitle=t("components:user_config._llm.configureAnLlmEndpointForIntelligentMaintenanceLabeling"),
        icon=ft.Icons.SMART_TOY,
        initially_expanded=False,
        content_controls=[
            ft.Row([llm_format, fetch_btn, verify_btn], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            llm_url,
            llm_api_key,
            llm_model,
            llm_verify_result,
            llm_test_result,
            ft.Row(action_buttons, spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
            llm_status,
        ],
    )

    return llm_card, {
        "reload": _reload_llm,
        "save": _save_llm,
        "reset": _reset_llm,
    }
