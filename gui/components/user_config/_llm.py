"""LLM 标注配置区域组件。"""
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

    llm_url = ft.TextField(label=t("components:user_config._llm.接口URL_71a3"), hint_text="https://api.example.com/v1", expand=True, color=theme.TEXT_PRIMARY)
    llm_api_key = ft.TextField(label="API Key", password=True, can_reveal_password=True, expand=True, color=theme.TEXT_PRIMARY)
    llm_model = ft.Dropdown(label=t("components:user_config._llm.模型_8000"), expand=True, options=[], hint_text=t("components:user_config._llm.点击「获取模型」加载列表_c38d"), editable=True)
    llm_format = ft.Dropdown(
        label=t("components:user_config._llm.接口格式_3471"),
        width=160,
        options=[
            ft.dropdown.Option("openai", t("components:user_config._llm.OpenAI兼容_a2fb")),
            ft.dropdown.Option("anthropic", "Anthropic"),
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
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

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
            llm_test_result.value = t("components:user_config._llm.请先填写接口URL_fd01")
            llm_test_result.color = ft.Colors.RED
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return
        llm_test_result.value = t("components:user_config._llm.正在获取模型列表..._9167")
        llm_test_result.color = theme.TEXT_SECONDARY
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

        def _do_fetch():
            result = config_loader.test_llm_connection(cfg)
            def _update():
                if result["success"]:
                    models = result["models"]
                    llm_model.options = [ft.dropdown.Option(m) for m in models]
                    if models and not llm_model.value:
                        llm_model.value = models[0]
                    info = result.get("error", "")
                    if models:
                        llm_test_result.value = t("components:user_config._llm.获取到个模型_ef8a", count=len(models))
                        llm_test_result.color = theme.TEXT_PRIMARY
                        _log_message(log, t("components:user_config._llm.获取到个可用模型_2492", count=len(models)))
                    else:
                        llm_test_result.value = info or t("components:user_config._llm.未返回模型，请手动输入模型名称_4683")
                        llm_test_result.color = ft.Colors.ORANGE
                        _log_message(log, info or t("components:user_config._llm.接口未返回模型列表，可手动输入_62ea"))
                else:
                    llm_test_result.value = t("components:user_config._llm.连接失败:_bb44", error=result['error'])
                    llm_test_result.color = ft.Colors.RED
                    _log_message(log, t("components:user_config._llm.LLM接口连接失败:_c328", error=result['error']), level=logging.ERROR)
                try:
                    page.update()
                except (RuntimeError, AttributeError):
                    pass
            _update()

        import threading
        threading.Thread(target=_do_fetch, daemon=True).start()

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
        llm_status.value = t("components:user_config._llm.LLM配置已保存_0e52")
        _log_message(log, t("components:user_config._llm.已保存LLM标注配置_c543"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    def _reset_llm(_e):
        config_loader.update_user_config({"llm_labeling": {}})
        _reload_llm()
        llm_status.value = t("components:user_config._llm.已恢复默认配置_455f")
        _log_message(log, t("components:user_config._llm.已重置LLM标注配置_c20c"))
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

    fetch_btn = theme.secondary_btn(t("components:user_config._llm.获取模型_9259"), icon=ft.Icons.REFRESH, on_click=_fetch_models)

    def _verify_connection(_e):
        cfg = {
            "url": (llm_url.value or "").strip(),
            "api_key": _resolve_api_key(),
            "format": llm_format.value or "openai",
        }
        if not cfg["url"]:
            llm_verify_result.value = t("components:user_config._llm.⚠请先填写接口URL_998d")
            llm_verify_result.color = ft.Colors.AMBER
            try:
                page.update()
            except (RuntimeError, AttributeError):
                pass
            return
        llm_verify_result.value = t("components:user_config._llm.正在验证..._59e6")
        llm_verify_result.color = theme.TEXT_SECONDARY
        try:
            page.update()
        except (RuntimeError, AttributeError):
            pass

        def _do_verify():
            result = config_loader.test_llm_connection(cfg)
            selected_model = (llm_model.value or "").strip()

            def _update():
                if result["success"]:
                    models = result["models"]
                    if selected_model and selected_model not in models:
                        llm_verify_result.value = t("components:user_config._llm.⚠连接成功，但所选模型「」_bf74", selected_model=selected_model, count=len(models))
                        llm_verify_result.color = ft.Colors.AMBER
                    else:
                        model_info = t("components:user_config._llm.，模型「」可用_3be5", selected_model=selected_model) if selected_model else ""
                        llm_verify_result.value = t("components:user_config._llm.✓连接成功（个模型可用）_f10d", count=len(models), model_info=model_info)
                        llm_verify_result.color = ft.Colors.GREEN
                else:
                    llm_verify_result.value = t("components:user_config._llm.✗连接失败:_3890", error=result['error'])
                    llm_verify_result.color = ft.Colors.RED
                try:
                    page.update()
                except (RuntimeError, AttributeError):
                    pass

            _update()

        import threading
        threading.Thread(target=_do_verify, daemon=True).start()

    verify_btn = theme.secondary_btn(t("components:user_config._llm.验证连接_c476"), icon=ft.Icons.CHECK_CIRCLE, on_click=_verify_connection)
    action_buttons = [
        theme.primary_btn(t("components:user_config._llm.保存配置_ed75"), icon=ft.Icons.SAVE, on_click=_save_llm),
        theme.secondary_btn(t("components:user_config._llm.重新加载_64ca"), icon=ft.Icons.REFRESH, on_click=lambda _: _reload_llm()),
        theme.secondary_btn(t("components:user_config._llm.恢复默认_7468"), icon=ft.Icons.RESTART_ALT, on_click=_reset_llm),
    ]

    llm_card = theme.make_collapsible(
        title=t("components:user_config._llm.LLM标注配置_4aee"),
        subtitle=t("components:user_config._llm.配置大模型接口用于维修记录智能_8504"),
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
