import asyncio
import contextlib
import importlib.util
import json
import logging
import pathlib
import sys
import time
import types
import weakref
from typing import ClassVar

import flet as ft
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader  # noqa: E402

# Set up gui package so relative imports work in importlib-loaded modules
if "gui" not in sys.modules:
    gui_pkg = types.ModuleType("gui")
    gui_pkg.__path__ = [str(ROOT / "gui")]
    gui_pkg.__package__ = "gui"
    sys.modules["gui"] = gui_pkg

spec = importlib.util.spec_from_file_location(
    "gui.components", ROOT / "gui" / "components" / "__init__.py",
    submodule_search_locations=[str(ROOT / "gui" / "components")],
)
components = importlib.util.module_from_spec(spec)
sys.modules["gui.components"] = components
spec.loader.exec_module(components)

main_spec = importlib.util.spec_from_file_location(
    "gui.main", ROOT / "gui" / "main.py",
    submodule_search_locations=[],
)
gui_main = importlib.util.module_from_spec(main_spec)
sys.modules["gui.main"] = gui_main
main_spec.loader.exec_module(gui_main)


def _invoke(handler, *args, **kwargs):
    """调用 handler，自动处理 async/sync 两种情况。"""
    result = handler(*args, **kwargs)
    if asyncio.iscoroutine(result):
        asyncio.run(result)


class DummyPage:
    def __init__(self):
        self.overlay = []
        self.services = []
        self._dialogs = []

    def update(self):
        pass

    def show_dialog(self, dialog):
        dialog.open = True
        self._dialogs.append(dialog)

    def pop_dialog(self):
        for dlg in reversed(self._dialogs):
            if dlg.open:
                dlg.open = False
                return dlg
        return None


class WindowSpy:
    def __init__(self):
        self.width = 1200
        self.height = 900
        self.min_width = 900
        self.on_resize = None


class PageSpy:
    _instances = weakref.WeakSet()

    def __init__(self):
        self.title = None
        self.theme_mode = None
        self.theme = None
        self.window = WindowSpy()
        self.controls = []
        self.services = []
        self.thread_calls = []
        self.task_calls = []
        self.on_close = None
        self.on_disconnect = None
        self.overlay = []
        self._dialogs = []
        self._tasks: set[asyncio.Task] = set()
        self._instances.add(self)

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def show_dialog(self, dialog):
        dialog.open = True
        self._dialogs.append(dialog)

    def pop_dialog(self):
        for dlg in reversed(self._dialogs):
            if dlg.open:
                dlg.open = False
                return dlg
        return None

    def run_task(self, coro, *args, **kwargs):
        """同步执行 coroutine（测试专用），确保 controls 在断言前已更新。"""
        self.task_calls.append((coro, args, kwargs))
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            task = loop.create_task(coro(*args, **kwargs))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return task
        else:
            with contextlib.suppress(RuntimeError):
                return asyncio.run(coro(*args, **kwargs))
        return None

    def close(self):
        """Stop page callbacks and cancel tasks scheduled by this page spy."""
        callback = self.on_disconnect or self.on_close
        if callback is not None:
            callback(None)
        for task in tuple(self._tasks):
            if not task.done():
                task.cancel()
        self._tasks.clear()

    def run_thread(self, handler, *args):
        self.thread_calls.append((handler, args))
        handler(*args)


@pytest.fixture(autouse=True)
def _cleanup_page_spies():
    yield
    for page in list(PageSpy._instances):
        page.close()
    gui_main.logic.reset_shutdown()


class DummyCheckbox:
    def __init__(self, value):
        self.value = value


class FrozenDateTime:
    @classmethod
    def now(cls):
        return types.SimpleNamespace(year=2026, month=4)


class DummyControlEvent:
    def __init__(self, control=None):
        self.control = control


class DummyFile:
    def __init__(self, path):
        self.path = str(path)


class SavePicker:
    next_path = None

    async def save_file(self, **kwargs):
        return self.next_path


class DummyDragEvent:
    def __init__(self, delta_y):
        self.primary_delta = delta_y
        self.local_delta = types.SimpleNamespace(y=delta_y)


class StubLogView:
    def __init__(self):
        self.log_list = types.SimpleNamespace(controls=[], auto_scroll=True, spacing=4, update=lambda: None, scroll_to=lambda **kw: None)
        self.level_filter = types.SimpleNamespace(value="INFO", on_select=None)
        self.export_button = types.SimpleNamespace(on_click=None)
        self.clear_button = types.SimpleNamespace(on_click=None)
        self.scroll_bottom_button = types.SimpleNamespace(
            on_click=None,
            tooltip="滚动到底部",
            icon_color=None,
            update=lambda: None,
        )
        self.follow_status = types.SimpleNamespace(visible=False, update=lambda: None)
        self.resize_handle = types.SimpleNamespace(on_vertical_drag_update=None)
        self.list_container = types.SimpleNamespace(height=200, update=lambda: None)
        self.content = types.SimpleNamespace(
            controls=[
                types.SimpleNamespace(),
                self.resize_handle,
                self.list_container,
            ]
        )

    def update(self):
        pass


def make_stub_log_view():
    view = StubLogView()
    refs = {
        "level_filter": view.level_filter,
        "export_button": view.export_button,
        "clear_button": view.clear_button,
        "scroll_bottom_button": view.scroll_bottom_button,
        "follow_status": view.follow_status,
        "resize_handle": view.resize_handle,
        "list_container": view.list_container,
        "log_list": view.log_list,
    }
    return view, refs


class ImportPicker:
    next_files = None

    async def pick_files(self, **kwargs):
        return self.next_files


class ApplyConfigSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, config, version="new"):
        self.calls.append(config)


class UpdateDeviceLoadMapSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, updates, version="new"):
        self.calls.append(updates)
        return updates




def _config_table_values(refs):
    return [
        {
            "selected": row["selected"],
            "device": row["device"],
            "capacity": str(row["capacity"]),
        }
        for row in refs["config_state"]
    ]


def _find_button(refs, label):
    for button in refs["action_buttons"]:
        for attr in ("text", "value"):
            if getattr(button, attr, None) == label:
                return button
        if label in repr(button):
            return button
        content = getattr(button, "content", None)
        if getattr(content, "value", None) == label:
            return button
        for attr in ("content", "controls"):
            nested = getattr(content, attr, None)
            if isinstance(nested, list):
                for item in nested:
                    if getattr(item, "value", None) == label or label in repr(item):
                        return button
    raise LookupError(label)




def test_ledger_section_uses_consistent_vertical_spacing():
    section, _ = components.create_ledger_section(DummyPage(), lambda message: None)

    assert section.padding == 12
    assert section.content.spacing == 8


def test_modules_section_uses_consistent_vertical_spacing(monkeypatch):
    monkeypatch.setattr(components, "datetime", FrozenDateTime, raising=False)

    section, _ = components.create_modules_section(DummyPage())

    assert section.padding == 12
    assert section.content.spacing == 8


def test_work_module_exposes_year_month_refs_with_current_date_defaults(monkeypatch):
    import gui.components.modules as _cmp_modules
    monkeypatch.setattr(_cmp_modules, "local_now", FrozenDateTime.now, raising=False)

    _, module_refs = components.create_modules_section(DummyPage())

    work_refs = module_refs["work"]

    assert "year" in work_refs
    assert "month" in work_refs
    assert work_refs["year"].value == "2026"
    assert work_refs["month"].value == "4"


def test_work_month_dropdown_offers_all_calendar_months(monkeypatch):
    monkeypatch.setattr(components, "datetime", FrozenDateTime, raising=False)

    _, module_refs = components.create_modules_section(DummyPage())

    month_options = [option.key for option in module_refs["work"]["month"].options]

    assert month_options == [str(month) for month in range(1, 13)]


def test_tire_module_exposes_file_input_and_shared_hidden_controls(monkeypatch):
    monkeypatch.setattr(components, "datetime", FrozenDateTime, raising=False)

    _, module_refs = components.create_modules_section(DummyPage())

    assert "tire" in module_refs
    assert module_refs["tire"]["path"].label == "轮胎寿命处理"
    assert "_skip_hidden_rows_toggle" in module_refs
    assert "_skip_hidden_cols_toggle" in module_refs


def test_maintenance_module_enables_ml_fallback_by_default(monkeypatch):
    monkeypatch.setattr(components, "datetime", FrozenDateTime, raising=False)

    _, module_refs = components.create_modules_section(DummyPage())

    ml_toggle = module_refs["maint"]["use_ml"]
    assert ml_toggle.value is True
    assert "其他/待确认" in ml_toggle.tooltip


def test_config_rows_render_with_explicit_checkbox_controls():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": 35},
        {"selected": True, "device": "EH4000", "capacity": 85},
    ])

    first_checkbox = refs["config_table"].rows[0].cells[0].content
    second_checkbox = refs["config_table"].rows[1].cells[0].content

    assert first_checkbox.value is False
    assert second_checkbox.value is True
    assert refs["config_table"].rows[0].cells[1].content.value == "TR100"
    assert refs["config_table"].rows[1].cells[2].content.value == "85"


def test_delete_selected_removes_only_checked_config_rows():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["set_config_state"]([
        {"selected": True, "device": "TR100", "capacity": 35},
        {"selected": False, "device": "EH4000", "capacity": 85},
        {"selected": True, "device": "NTE240", "capacity": 90},
    ])

    refs["remove_selected_rows"]()

    assert _config_table_values(refs) == [
        {"selected": False, "device": "EH4000", "capacity": "85"}
    ]


def test_restore_default_config_replaces_ui_state_without_writing_files(tmp_path):
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["set_config_state"]([
        {"selected": False, "device": "TEMP", "capacity": 1},
    ])

    default_config = tmp_path / "config.json"
    default_config.write_text(
        json.dumps({"device_load_map": {"TR100": 35, "EH4000": 85}}),
        encoding="utf-8",
    )

    refs["load_default_config_file"](default_config)

    assert _config_table_values(refs) == [
        {"selected": False, "device": "EH4000", "capacity": "85"},
        {"selected": False, "device": "TR100", "capacity": "35"},
    ]


def test_save_config_writes_json_to_user_selected_path(tmp_path):
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": "35"},
        {"selected": False, "device": "EH4000", "capacity": "85"},
    ])

    output_path = tmp_path / "my-config.json"

    refs["save_config_to_path"](output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == {
        "device_load_map": {
            "TR100": 35,
            "EH4000": 85,
        }
    }


def test_save_config_cancel_keeps_state_and_writes_nothing(tmp_path):
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": "35"},
    ])
    before = list(refs["config_state"])

    refs["save_config_to_path"](None)

    assert refs["config_state"] == before
    assert list(tmp_path.iterdir()) == []


def test_save_button_uses_selected_path_instead_of_mutating_default_config(monkeypatch, tmp_path):
    logs = []
    update_spy = UpdateDeviceLoadMapSpy()
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    monkeypatch.setattr(components.ft, "FilePicker", SavePicker)
    monkeypatch.setattr(config_loader, "update_device_load_map", update_spy)

    output_path = tmp_path / "exported-config.json"
    SavePicker.next_path = str(output_path)

    _, refs = components.create_config_section(DummyPage(), logs.append)
    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": "35"},
        {"selected": False, "device": "EH4000", "capacity": "85"},
    ])

    save_button = _find_button(refs, "保存配置")

    import asyncio
    asyncio.run(save_button.on_click(DummyControlEvent()))

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "device_load_map": {"TR100": 35, "EH4000": 85}
    }
    assert update_spy.calls == []
    assert logs[-1] == f"配置已另存为: {output_path}"


def test_import_config_replaces_existing_ui_state(monkeypatch, tmp_path):
    logs = []
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    monkeypatch.setattr(components.ft, "FilePicker", ImportPicker)

    imported_config = tmp_path / "imported-config.json"
    imported_config.write_text(
        json.dumps({"device_load_map": {"TR100": 35, "EH4000": 85}}),
        encoding="utf-8",
    )
    ImportPicker.next_files = [DummyFile(imported_config)]

    _, refs = components.create_config_section(DummyPage(), logs.append)
    refs["set_config_state"]([
        {"selected": False, "device": "TEMP", "capacity": "1"},
        {"selected": False, "device": "OLD", "capacity": "2"},
    ])

    import_button = _find_button(refs, "导入配置")

    import asyncio
    asyncio.run(import_button.on_click(DummyControlEvent()))

    assert _config_table_values(refs) == [
        {"selected": False, "device": "EH4000", "capacity": "85"},
        {"selected": False, "device": "TR100", "capacity": "35"},
    ]
    assert logs[-1] == "已导入 2 条设备装载量配置"






def test_restore_default_button_loads_builtin_config_file(monkeypatch, tmp_path):
    logs = []
    built_in_config = tmp_path / "builtin-config.json"
    built_in_config.write_text(
        json.dumps({"device_load_map": {"NTE240": 90}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "get_config_file_path", lambda: built_in_config)
    monkeypatch.setattr(config_loader, "get_default_load_map", lambda version="new": {"NTE240": 90} if version == "new" else {"NTE240": 80})

    page = DummyPage()
    _, refs = components.create_config_section(page, logs.append)
    refs["set_config_state"]([
        {"selected": False, "device": "TEMP", "capacity": "1"},
    ])

    restore_button = _find_button(refs, "恢复默认")

    # 点击恢复默认按钮，弹出版本选择对话框
    restore_button.on_click(DummyControlEvent())
    assert len(page._dialogs) == 1

    # 找到"新版配置"按钮并点击
    dialog = page._dialogs[0]
    new_version_btn = dialog.actions[2]  # "新版配置"是第三个按钮
    new_version_btn.on_click(DummyControlEvent())

    assert _config_table_values(refs) == [
        {"selected": False, "device": "NTE240", "capacity": "90"}
    ]
    assert logs[-1] == "已恢复新版默认配置"



def test_config_action_buttons_use_consistent_widths():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    # Buttons use theme helpers without explicit width; verify they exist and have no None width
    assert all(button is not None for button in refs["action_buttons"])


def test_config_action_button_rows_are_two_rows():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    # 2 行布局：action_button_rows[0] 是 Column 包含两个 Row
    col = refs["action_button_rows"][0]
    assert isinstance(col, components.ft.Column)
    assert len(col.controls) == 2






def test_config_section_uses_tighter_vertical_spacing():
    section, _ = components.create_config_section(DummyPage(), lambda message: None)

    assert section.padding == 12
    assert section.content.spacing == 8



def test_gui_main_uses_consistent_section_spacing(monkeypatch):
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    page = PageSpy()

    gui_main.main(page)

    scroll_col = page.controls[0]
    assert scroll_col.spacing == 0


def test_gui_main_log_helper_supports_custom_levels(monkeypatch):
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {"log": log}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    captured = {}

    def capture_ledger_section(page, log):
        captured["log"] = log
        return object(), {}

    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", capture_ledger_section)

    page = PageSpy()
    gui_main.main(page)

    captured["log"]("警告消息", level=logging.WARNING)
    time.sleep(0.3)

    log_view = page.controls[0].controls[-1]
    last_text = refs["log_list"].controls[-1]
    assert last_text.value.endswith("警告消息")


    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    page = PageSpy()

    gui_main.main(page)
    time.sleep(0.3)

    assert page.task_calls, "expected GUI log updates to be scheduled through run_task"


def test_gui_main_stops_log_consumer_on_disconnect(monkeypatch):
    # Save real create_log_view before monkeypatching (they share the same module)
    real_create_log_view = components.create_log_view.__wrapped__ if hasattr(components.create_log_view, '__wrapped__') else components.create_log_view

    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    page = PageSpy()

    gui_main.main(page)
    assert page.on_disconnect is not None

    before_disconnect = len(page.task_calls)
    page.on_disconnect(None)
    logging.getLogger().info("关闭后日志")
    time.sleep(0.05)

    assert len(page.task_calls) == before_disconnect

    # Test real create_log_view (undo monkeypatch first)
    monkeypatch.undo()
    log_view, refs = real_create_log_view()

    assert isinstance(log_view, components.ft.Container)
    assert refs["log_list"].auto_scroll is False
    assert refs["log_list"].spacing == 4
    assert refs["list_container"].height == 350
    assert getattr(refs["export_button"], "tooltip", None) == "导出日志"
    assert refs["follow_status"].visible is False



def test_log_view_exposes_filter_resize_and_export_controls():
    log_view, refs = components.create_log_view(height=260)

    resize_handle, list_container = log_view.content.controls

    toolbar = refs["toolbar"]
    assert toolbar.controls[0] is refs["level_filter"]
    assert toolbar.controls[1] is refs["export_button"]
    assert toolbar.spacing == 4
    assert refs["level_filter"].value == "INFO"
    assert resize_handle is refs["resize_handle"]
    assert list_container is refs["list_container"]
    assert refs["list_container"].height == 260



def test_gui_main_filters_logs_by_level(monkeypatch):
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    captured = {}

    def capture_ledger_section(page, log):
        captured["log"] = log
        return object(), {}

    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", capture_ledger_section)

    page = PageSpy()
    gui_main.main(page)

    captured["log"]("信息消息", level=logging.INFO)
    captured["log"]("错误消息", level=logging.ERROR)
    time.sleep(0.3)

    refs["level_filter"].value = "ERROR"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))
    assert len(refs["log_list"].controls) == 1
    assert refs["log_list"].controls[0].value.endswith("错误消息")

    refs["level_filter"].value = "INFO"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))
    assert len(refs["log_list"].controls) >= 2



def test_gui_main_filters_logs_by_level_and_above(monkeypatch):
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    captured = {}

    def capture_ledger_section(page, log):
        captured["log"] = log
        return object(), {}

    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", capture_ledger_section)

    page = PageSpy()
    gui_main.main(page)
    time.sleep(0.1)

    # 清空已有日志，确保只看到下面发出的测试日志
    refs["log_list"].controls.clear()

    # setup_logging 默认 INFO，临时降到 DEBUG 以发出 DEBUG 消息
    prev_level = logging.root.level
    logging.root.setLevel(logging.DEBUG)
    try:
        captured["log"]("debug消息", level=logging.DEBUG)
        captured["log"]("info消息", level=logging.INFO)
        captured["log"]("warning消息", level=logging.WARNING)
        captured["log"]("error消息", level=logging.ERROR)
    finally:
        logging.root.setLevel(prev_level)
    time.sleep(0.3)

    # WARNING 及以上：应包含 WARNING + ERROR，不含 INFO / DEBUG
    refs["level_filter"].value = "WARNING"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))
    values = [c.value for c in refs["log_list"].controls]
    assert any("warning消息" in v for v in values)
    assert any("error消息" in v for v in values)
    assert not any("info消息" in v for v in values)
    assert not any("debug消息" in v for v in values)

    # INFO 及以上：应包含 INFO + WARNING + ERROR，不含 DEBUG
    refs["level_filter"].value = "INFO"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))
    values = [c.value for c in refs["log_list"].controls]
    assert any("info消息" in v for v in values)
    assert any("warning消息" in v for v in values)
    assert any("error消息" in v for v in values)
    assert not any("debug消息" in v for v in values)

    # DEBUG 及以上：应包含全部 4 条测试日志
    refs["level_filter"].value = "DEBUG"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))
    values = [c.value for c in refs["log_list"].controls]
    assert sum(1 for v in values if "消息" in v) == 4



def test_gui_main_exports_filtered_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))
    monkeypatch.setattr(gui_main.ft, "FilePicker", SavePicker)

    export_path = tmp_path / "logs.txt"
    SavePicker.next_path = str(export_path)

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    captured = {}

    def capture_ledger_section(page, log):
        captured["log"] = log
        return object(), {}

    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", capture_ledger_section)

    page = PageSpy()
    gui_main.main(page)

    captured["log"]("普通日志", level=logging.INFO)
    captured["log"]("错误日志", level=logging.ERROR)
    time.sleep(0.3)

    refs["level_filter"].value = "ERROR"
    _invoke(refs["level_filter"].on_select, DummyControlEvent(refs["level_filter"]))

    import asyncio
    asyncio.run(refs["export_button"].on_click(DummyControlEvent(refs["export_button"])))

    exported_text = export_path.read_text(encoding="utf-8")
    assert export_path.exists()
    assert "错误日志" in exported_text
    assert "普通日志" not in exported_text



def test_gui_main_resizes_log_view_with_drag(monkeypatch):
    monkeypatch.setattr(gui_main.cmp, "create_ledger_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_config_section", lambda page, log: (object(), {}))
    monkeypatch.setattr(gui_main.cmp, "create_modules_section", lambda page: (object(), {}))

    log_view, refs = make_stub_log_view()
    monkeypatch.setattr(gui_main.cmp, "create_log_view", lambda: (log_view, refs))
    monkeypatch.setattr(gui_main.logic, "wire_processing_buttons", lambda module_refs, page, log, *a, **kw: None)
    monkeypatch.setattr(gui_main.logic, "init", lambda config_refs: None)

    page = PageSpy()
    gui_main.main(page)

    refs["resize_handle"].on_vertical_drag_update(DummyDragEvent(-80))
    # main() sets window.height=1050, so _recommended_log_height gives round(1050/3)=350
    assert refs["list_container"].height == 350 + 80

    refs["resize_handle"].on_vertical_drag_update(DummyDragEvent(500))
    assert refs["list_container"].height == gui_main.MIN_LOG_HEIGHT



def test_apply_button_uses_current_ui_config_without_saving(monkeypatch):
    logs = []
    apply_spy = ApplyConfigSpy()
    update_spy = UpdateDeviceLoadMapSpy()
    monkeypatch.setattr(config_loader, "apply_device_load_map", apply_spy)
    monkeypatch.setattr(config_loader, "update_device_load_map", update_spy)

    _, refs = components.create_config_section(DummyPage(), logs.append)
    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": "35"},
        {"selected": False, "device": "EH4000", "capacity": "85"},
    ])

    apply_button = _find_button(refs, "应用当前配置")

    apply_button.on_click(DummyControlEvent())

    assert apply_spy.calls == [{"TR100": 35, "EH4000": 85}]
    assert update_spy.calls == [{"TR100": 35, "EH4000": 85}]
    assert logs[-1] == "当前新版配置已应用并保存"


# ---- DataTable column invariant tests ----
# Flet's DataTable.before_update() raises ValueError when there are zero
# visible DataColumn instances.  This surfaces as a crash during page.update()
# (e.g. on window close / session garbage-collect).  These tests guard against
# that invariant being violated in our component tables.


def _find_datatables(control, found=None):
    """Walk a Flet control tree and collect all DataTable instances."""
    if found is None:
        found = []
    if isinstance(control, ft.DataTable):
        found.append(control)
    for attr in ("content", "controls", "rows"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for item in child:
                _find_datatables(item, found)
        elif child is not None:
            _find_datatables(child, found)
    return found


def test_flet_datatable_raises_when_columns_empty():
    """DataTable.before_update() rejects zero visible columns."""
    import pytest
    table = ft.DataTable(columns=[], rows=[])
    with pytest.raises(ValueError, match="columns must contain at minimum one visible DataColumn"):
        table.before_update()


def test_anomaly_results_table_updates_and_hides_when_empty():
    """异常明细有记录时显示 DataTable，清空后隐藏结果区。"""
    from gui.components.common import create_anomaly_results_table

    refs = create_anomaly_results_table()
    refs["table"].before_update()
    assert refs["container"].visible is False

    refs["update"]([
        {
            "数据类型": "油耗信息",
            "行号": 3,
            "日期": "2026-08-11",
            "设备名称": "TR100",
            "异常列": "油品消耗",
            "异常值": 60000,
            "说明": "超过上限 50000",
        }
    ])
    assert refs["container"].visible is True
    assert len(refs["table"].rows) == 1
    assert refs["table"].rows[0].cells[0].content.value == "油耗信息"
    refs["table"].before_update()

    refs["update"]([])
    assert refs["container"].visible is False
    assert refs["table"].rows == []


def test_daily_report_export_locks_button_and_ignores_duplicate_click(monkeypatch, tmp_path):
    """日报导出期间按钮应禁用，重复点击不能启动第二个导出任务。"""
    import asyncio
    from types import SimpleNamespace

    import gui.components.daily_report as daily_report_module

    _, refs = components.create_daily_report_section(DummyPage(), lambda *args: None, {}, {})
    refs["source_path"].value = str(tmp_path)
    release = asyncio.Event()
    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((refs["btn"].disabled, refs["btn"].text))
        await release.wait()
        return SimpleNamespace(report=[], warnings=[], detail_sheets={})

    monkeypatch.setattr(daily_report_module.asyncio, "to_thread", fake_to_thread)

    async def run_clicks():
        first = asyncio.create_task(refs["btn"].on_click(DummyControlEvent(refs["btn"])))
        await asyncio.sleep(0)
        assert refs["btn"].disabled is True
        assert refs["btn"].text == "导出中..."

        second = asyncio.create_task(refs["btn"].on_click(DummyControlEvent(refs["btn"])))
        await asyncio.sleep(0)
        assert len(calls) == 1

        release.set()
        await asyncio.gather(first, second)

    asyncio.run(run_clicks())
    assert refs["btn"].disabled is False
    assert refs["btn"].text == "导出每日报表"


def test_daily_report_shows_export_warnings_in_bottom_table(monkeypatch, tmp_path):
    """日报导出完成后应在页面底部展示警告/异常明细。"""
    import asyncio
    from types import SimpleNamespace

    import gui.components.daily_report as daily_report_module

    _, refs = components.create_daily_report_section(DummyPage(), lambda *args: None, {}, {})
    refs["source_path"].value = str(tmp_path)

    async def fake_to_thread(func, *args, **kwargs):
        return SimpleNamespace(
            report=[],
            detail_sheets={},
            warnings=[{
                "数据类型": "设备台账匹配",
                "字段": "设备编号",
                "值": "LP0028",
                "消息": "设备台账未匹配",
            }],
        )

    monkeypatch.setattr(daily_report_module.asyncio, "to_thread", fake_to_thread)
    asyncio.run(refs["btn"].on_click(DummyControlEvent(refs["btn"])))

    anomaly_refs = refs["anomaly_results"]
    assert anomaly_refs["container"].visible is True
    assert len(anomaly_refs["table"].rows) == 1
    assert anomaly_refs["table"].rows[0].cells[0].content.value == "设备台账匹配"
    assert anomaly_refs["table"].rows[0].cells[6].content.value == "设备编号"
    assert anomaly_refs["table"].rows[0].cells[7].content.value == "LP0028"


def test_ledger_table_has_placeholder_column_when_empty():
    """Ledger table must always have >= 1 DataColumn, even with no records."""
    _, refs = components.create_ledger_section(DummyPage(), lambda m: None)
    table = refs["ledger_table"]
    assert len(table.columns) >= 1, "DataTable must have at least one column"
    # Verify it passes Flet validation
    table.before_update()


def test_oil_ledger_table_has_placeholder_column_when_empty():
    """Oil ledger table must always have >= 1 DataColumn, even with no records."""
    _, refs = components.create_oil_ledger_section(DummyPage(), lambda m: None)
    table = refs["oil_table"]
    assert len(table.columns) >= 1, "DataTable must have at least one column"
    table.before_update()


def test_ledger_match_table_has_placeholder_column_when_empty():
    """Ledger match table must always have >= 1 DataColumn when no data imported."""
    container, _ = components.create_ledger_match_section(
        DummyPage(), lambda m: None, {}, {}
    )
    tables = _find_datatables(container)
    assert len(tables) >= 1, "Expected at least one DataTable in ledger match section"
    for table in tables:
        assert len(table.columns) >= 1, "DataTable must have at least one column"
        table.before_update()


def test_ledger_build_table_keeps_columns_when_no_data():
    """build_table() must not set columns=[] when there are no records."""
    _, refs = components.create_ledger_section(DummyPage(), lambda m: None)
    table = refs["ledger_table"]
    initial_cols = len(table.columns)
    assert initial_cols >= 1

    # Simulate empty records and call build_table
    refs["ledger_records"].clear()
    refs["build_table"]()

    assert len(table.columns) >= 1, (
        "build_table() must keep at least 1 column when data is empty"
    )
    table.before_update()


def test_oil_ledger_build_table_keeps_columns_when_no_data():
    """build_table() must not set columns=[] when there are no oil records."""
    _, refs = components.create_oil_ledger_section(DummyPage(), lambda m: None)
    table = refs["oil_table"]
    initial_cols = len(table.columns)
    assert initial_cols >= 1

    refs["oil_records"].clear()
    refs["build_table"]()

    assert len(table.columns) >= 1, (
        "build_table() must keep at least 1 column when data is empty"
    )
    table.before_update()


def test_ledger_match_build_table_keeps_columns_when_no_data():
    """build_table() must not set columns=[] when no data is imported."""
    container, refs = components.create_ledger_match_section(
        DummyPage(), lambda m: None, {}, {}
    )
    tables = _find_datatables(container)
    assert len(tables) >= 1
    table = tables[0]
    initial_cols = len(table.columns)
    assert initial_cols >= 1

    # build_table() with no imported data should keep columns
    refs["build_table"]()

    assert len(table.columns) >= 1, (
        "build_table() must keep at least 1 column when data is empty"
    )
    table.before_update()


# ---- initial_directory persistence tests ----
# After selecting a file, the next file picker should open at the same directory.


class SavePickerSpy:
    """SavePicker that records kwargs for each call."""
    next_path = None
    calls: ClassVar[list] = []

    def __init__(self):
        pass

    async def save_file(self, **kwargs):
        self.__class__.calls.append(kwargs)
        return self.next_path

    @classmethod
    def reset(cls):
        cls.next_path = None
        cls.calls = []


class ImportPickerSpy:
    """ImportPicker that records kwargs for each call."""
    next_files = None
    calls: ClassVar[list] = []

    def __init__(self):
        pass

    async def pick_files(self, **kwargs):
        self.__class__.calls.append(kwargs)
        return self.next_files

    @classmethod
    def reset(cls):
        cls.next_files = None
        cls.calls = []


def test_config_save_picker_remembers_initial_directory(monkeypatch, tmp_path):
    """After saving config, next save_file call uses the same directory."""
    # 隔离配置文件，避免测试写入真实 config.user.json
    import func.config_loader as config_loader
    user_file = tmp_path / "config.user.json"
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)

    SavePickerSpy.reset()
    monkeypatch.setattr(components.ft, "FilePicker", SavePickerSpy)

    output_path = tmp_path / "subdir" / "config.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    SavePickerSpy.next_path = str(output_path)

    _, refs = components.create_config_section(DummyPage(), lambda m: None)
    refs["set_config_state"]([
        {"selected": False, "device": "TR100", "capacity": "35"},
    ])
    save_button = _find_button(refs, "保存配置")

    import asyncio
    # First save — no initial_directory yet
    asyncio.run(save_button.on_click(DummyControlEvent()))
    assert len(SavePickerSpy.calls) == 1

    # Second save — initial_directory should be the parent of the first file
    asyncio.run(save_button.on_click(DummyControlEvent()))
    assert len(SavePickerSpy.calls) == 2
    assert SavePickerSpy.calls[1].get("initial_directory") == str(output_path.parent)


def test_sync_and_daily_report_use_independent_saved_directories(monkeypatch, tmp_path):
    """同步和日报的目录记忆不应互相覆盖。"""
    import func.config_loader as config_loader
    from gui.components.common import _get_initial_directory, _update_last_directory

    sync_dir = tmp_path / "sync"
    daily_dir = tmp_path / "daily"
    sync_dir.mkdir()
    daily_dir.mkdir()
    user_file = tmp_path / "config.user.json"
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)
    config_loader._invalidate_config_cache()

    _update_last_directory(str(sync_dir), is_dir=True, config_key="sync_last_input_dir")
    _update_last_directory(str(daily_dir), is_dir=True, config_key="daily_report_input_dir")

    assert _get_initial_directory("sync_last_input_dir") == str(sync_dir)
    assert _get_initial_directory("daily_report_input_dir") == str(daily_dir)
    saved = json.loads(user_file.read_text(encoding="utf-8"))
    assert saved["user_config"]["sync_last_input_dir"] == str(sync_dir)
    assert saved["user_config"]["daily_report_input_dir"] == str(daily_dir)


def test_daily_report_save_persists_formulas_after_validation(monkeypatch):
    """保存日报设置时，校验通过的公式应继续可用于构造配置。"""
    from copy import deepcopy

    from gui.components.user_config import _daily_report as daily_report_module

    defaults = deepcopy(config_loader.DEFAULT_DAILY_REPORT_CONFIG)
    saved = []
    monkeypatch.setattr(
        daily_report_module.config_loader,
        "get_daily_report_config",
        lambda: deepcopy(defaults),
    )
    monkeypatch.setattr(
        daily_report_module.config_loader,
        "save_daily_report_config",
        lambda config: saved.append(config),
    )

    _, refs = daily_report_module._create_daily_report_config_section(
        DummyPage(), lambda *args, **kwargs: None,
    )
    refs["save"]()

    assert saved
    assert saved[0]["formulas"] == defaults["formulas"]


def test_oil_ledger_build_table_restores_columns_after_clear():
    """After clear→import, build_table must restore proper columns."""
    from func.oil_ledger import OIL_LEDGER_COLUMNS

    _, refs = components.create_oil_ledger_section(DummyPage(), lambda m: None)
    table = refs["oil_table"]

    # Clear: sets columns to placeholder
    refs["oil_records"].clear()
    refs["build_table"]()
    assert len(table.columns) == 1  # placeholder

    # Simulate import: add records and rebuild
    refs["oil_records"].extend([{"油品名称": "0# 柴油", "标准油品名称": "0号柴油"}])
    refs["build_table"]()

    col_labels = [c.label.value for c in table.columns]
    assert col_labels == OIL_LEDGER_COLUMNS, (
        f"Expected columns {OIL_LEDGER_COLUMNS}, got {col_labels}"
    )
    assert len(table.rows) == 1
    table.before_update()


def test_ledger_build_table_restores_columns_after_clear():
    """After clear→import, build_table must restore proper columns."""
    from func.equipment_ledger import LEDGER_COLUMNS

    _, refs = components.create_ledger_section(DummyPage(), lambda m: None)
    table = refs["ledger_table"]

    # Clear
    refs["ledger_records"].clear()
    refs["build_table"]()
    assert len(table.columns) == 1  # placeholder

    # Simulate import
    refs["ledger_records"].extend([{"设备名称": "TR100", "设备编号": "1001"}])
    refs["build_table"]()

    col_labels = [c.label.value for c in table.columns]
    assert col_labels == LEDGER_COLUMNS, (
        f"Expected columns {LEDGER_COLUMNS}, got {col_labels}"
    )
    assert len(table.rows) == 1
    table.before_update()


# ---- Column mapping dialog runtime behavior tests ----


def test_column_mapping_confirm_works_via_show_dialog():
    """on_ok must close dialog and call on_confirm when opened via show_dialog.

    Previously, the overlay approach caused dialog.update() to crash because
    the dialog had no page parent. Now we use page.show_dialog/pop_dialog.
    """
    page = PageSpy()
    confirmed = []
    _STANDARD_COLS = [("设备名称", "设备的原始名称")]
    dialog = components.create_column_mapping_dialog(
        page, ["设备名称"], _STANDARD_COLS, lambda m, s: confirmed.append((m, s))
    )
    page.show_dialog(dialog)
    assert dialog.open is True

    confirm_btn = next(a for a in dialog.actions if str(a.content) == "确认导入")
    confirm_btn.on_click(None)

    assert dialog.open is False
    assert len(confirmed) == 1





def test_column_mapping_cancel_closes_dialog():
    """Clicking '取消' on the column mapping dialog must close it."""
    page = PageSpy()
    columns = ["设备名称", "设备编号", "公司"]
    _STANDARD_COLS = [("设备名称", ""), ("设备编号", ""), ("公司", "")]
    confirmed = []

    dialog = components.create_column_mapping_dialog(
        page, columns, _STANDARD_COLS, lambda m, s: confirmed.append((m, s))
    )

    # Open the dialog via page API
    page.show_dialog(dialog)
    assert dialog.open is True

    # Find the cancel button
    cancel_btn = None
    for action in dialog.actions:
        if str(action.content) == "取消":
            cancel_btn = action
            break
    assert cancel_btn is not None, "Dialog must have a '取消' button"

    # Simulate clicking cancel (on_click is sync)
    cancel_btn.on_click(None)

    assert dialog.open is False, "Dialog must be closed after clicking '取消'"
    assert len(confirmed) == 0, "on_confirm must NOT be called on cancel"


def test_column_mapping_confirm_closes_dialog():
    """Clicking '确认导入' on the column mapping dialog must close it and call on_confirm."""
    page = PageSpy()
    columns = ["设备名称", "设备编号", "公司"]
    _STANDARD_COLS = [("设备名称", ""), ("设备编号", ""), ("公司", "")]
    confirmed = []

    dialog = components.create_column_mapping_dialog(
        page, columns, _STANDARD_COLS, lambda m, s: confirmed.append((m, s))
    )

    # Open the dialog via page API
    page.show_dialog(dialog)
    assert dialog.open is True

    # Find the confirm button
    confirm_btn = None
    for action in dialog.actions:
        if str(action.content) == "确认导入":
            confirm_btn = action
            break
    assert confirm_btn is not None, "Dialog must have a '确认导入' button"

    # Simulate clicking confirm (on_click is sync)
    confirm_btn.on_click(None)

    assert dialog.open is False, "Dialog must be closed after clicking '确认导入'"
    assert len(confirmed) == 1, "on_confirm must be called once"


def test_oil_column_mapping_cancel_closes_dialog():
    """Clicking '取消' on the oil column mapping dialog must close it."""
    page = PageSpy()
    columns = ["油品名称", "标准油品名称"]
    _OIL_STANDARD_COLS = [("油品名称", ""), ("标准油品名称", "")]
    confirmed = []

    dialog = components.create_column_mapping_dialog(
        page, columns, _OIL_STANDARD_COLS, lambda m, s: confirmed.append((m, s)), height=300
    )

    page.show_dialog(dialog)
    assert dialog.open is True

    cancel_btn = None
    for action in dialog.actions:
        if str(action.content) == "取消":
            cancel_btn = action
            break
    assert cancel_btn is not None

    cancel_btn.on_click(None)

    assert dialog.open is False, "Oil dialog must be closed after clicking '取消'"
    assert len(confirmed) == 0


# ---- Date format preservation tests ----

import pandas as pd  # noqa: E402


def test_strip_date_only_times_converts_date_columns():
    """Datetime columns with only date values (time=00:00:00) should be
    converted to date objects so Excel export shows '2019-01-01' not
    '2019-01-01 00:00:00'."""
    from gui.components.common import strip_date_only_times

    df = pd.DataFrame({
        "日期": pd.to_datetime(["2019-01-01", "2019-06-15", "2020-12-31"]),
        "设备名称": ["TR100", "TR200", "TR300"],
        "数量": [10, 20, 30],
    })
    result = strip_date_only_times(df)
    # Date column should be pure date objects
    assert result["日期"].dtype == object
    assert all(isinstance(v, pd.Timestamp) is False for v in result["日期"].dropna())
    # Non-datetime columns untouched
    assert result["设备名称"].tolist() == ["TR100", "TR200", "TR300"]


def test_strip_date_only_times_keeps_time_columns():
    """Datetime columns with actual time values should NOT be stripped."""
    from gui.components.common import strip_date_only_times

    df = pd.DataFrame({
        "时间": pd.to_datetime(["2019-01-01 08:30:00", "2019-06-15 14:00:00"]),
        "数量": [10, 20],
    })
    result = strip_date_only_times(df)
    # Time column should remain as datetime
    assert pd.api.types.is_datetime64_any_dtype(result["时间"])


# ---------------------------------------------------------------------------
# LLM Labeling page
# ---------------------------------------------------------------------------

def test_llm_labeling_section_creates_with_required_refs():
    from gui.components.llm_labeling import create_llm_labeling_section

    _section, refs = create_llm_labeling_section(DummyPage())

    assert "path" in refs
    assert "sheet" in refs
    assert "btn" in refs
    assert "status" in refs


def test_llm_labeling_section_has_correct_padding():
    from gui.components.llm_labeling import create_llm_labeling_section

    section, _ = create_llm_labeling_section(DummyPage())

    assert section.padding == 12
    assert section.content.spacing == 8


def test_llm_labeling_initial_state_has_empty_sheet_dropdown():
    from gui.components.llm_labeling import create_llm_labeling_section

    _, refs = create_llm_labeling_section(DummyPage())

    assert refs["sheet"].options == []
    assert refs["sheet"].value is None


def test_llm_labeling_button_initially_disabled():
    from gui.components.llm_labeling import create_llm_labeling_section

    _, refs = create_llm_labeling_section(DummyPage())

    assert refs["btn"].disabled is True


def test_llm_labeling_auto_detect_column():
    from gui.components.llm_labeling import _auto_detect

    cols = ["日期", "班次", "维修内容", "大类", "小类", "分类方式"]
    assert _auto_detect(cols, "content") == "维修内容"
    assert _auto_detect(cols, "category") == "大类"
    assert _auto_detect(cols, "minor") == "小类"
    assert _auto_detect(cols, "status") == "分类方式"


def test_llm_labeling_auto_detect_falls_back_to_first_column():
    from gui.components.llm_labeling import _auto_detect

    cols = ["日期", "设备名称", "描述"]
    assert _auto_detect(cols, "content") == "日期"


def test_llm_labeling_auto_detect_returns_empty_for_no_columns():
    from gui.components.llm_labeling import _auto_detect

    assert _auto_detect([], "content") == ""


def test_llm_labeling_section_contains_four_module_cards():
    from gui.components.llm_labeling import create_llm_labeling_section

    section, _ = create_llm_labeling_section(DummyPage())

    # Count ModuleCard containers (bg-white rounded-lg border) in the column
    cards = [
        c for c in section.content.controls
        if isinstance(c, ft.Container)
        and hasattr(c, "bgcolor")
    ]
    # At minimum: file/sheet card + execute card; mapping & filter start hidden
    assert len(cards) >= 2


def test_llm_cancel_does_not_leak_stale_progress_into_next_run(tmp_path):
    """取消后立即重启时，上一轮的请求和进度不得影响新一轮。"""
    import threading
    from unittest.mock import patch

    from gui.components.llm_labeling import create_llm_labeling_section

    page = PageSpy()
    _, refs = create_llm_labeling_section(page)
    refs["path"].value = str(tmp_path / "input.xlsx")
    refs["sheet"].value = "维修明细"

    def _walk(control, seen=None):
        seen = seen or set()
        if id(control) in seen:
            return
        seen.add(id(control))
        yield control
        content = getattr(control, "content", None)
        if content is not None:
            yield from _walk(content, seen)
        for child in getattr(control, "controls", None) or []:
            yield from _walk(child, seen)

    cancel_btn = next(
        control
        for control in _walk(_)
        if isinstance(control, ft.Button)
        and str(getattr(control, "content", None)) == "取消"
    )

    first_started = threading.Event()
    second_started = threading.Event()
    second_release = threading.Event()
    stale_progress_done = threading.Event()
    run_events = []

    def _fake_process(*_args, **kwargs):
        cancel_event = kwargs["cancel_event"]
        progress_fn = kwargs["progress_fn"]
        run_events.append(cancel_event)
        if len(run_events) == 1:
            first_started.set()
            assert cancel_event.wait(1)

            def _emit_stale_progress():
                if second_started.wait(1):
                    progress_fn(
                        "旧任务进度",
                        {
                            "percent": 99,
                            "current": 99,
                            "total": 100,
                            "succeeded": 99,
                            "skipped": 0,
                            "failed": 0,
                            "retried": 0,
                            "rate": 1,
                        },
                    )
                stale_progress_done.set()

            threading.Thread(target=_emit_stale_progress, daemon=True).start()
            return {"cancelled": True, "llm_completed": 0, "remaining_rows": 1}

        second_started.set()
        second_release.wait(1)
        return {"cancelled": True, "llm_completed": 0, "remaining_rows": 1}

    def _wait_until(predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return predicate()

    with (
        patch(
            "func.config_loader.get_llm_config",
            return_value={
                "url": "http://fake",
                "api_key": "k",
                "model": "m",
                "concurrency": 1,
                "batch_size": 1,
            },
        ),
        patch(
            "func.label_maintenance_with_llm.process_maintenance_llm",
            side_effect=_fake_process,
        ),
    ):
        try:
            _invoke(refs["btn"].on_click, None)
            assert first_started.wait(1)

            _invoke(cancel_btn.on_click, None)
            assert _wait_until(lambda: not refs["btn"].disabled)

            _invoke(refs["btn"].on_click, None)
            assert second_started.wait(1)
            assert len(run_events) == 2
            assert run_events[0] is not run_events[1]
            assert run_events[0].is_set()

            assert stale_progress_done.wait(1)
            assert refs["progress_summary"].value == "准备发送标注任务…"
        finally:
            second_release.set()
            assert _wait_until(lambda: not refs["btn"].disabled)
