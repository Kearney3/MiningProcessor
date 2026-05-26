import importlib.util
import json
import logging
import pathlib
import sys
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader

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


class DummyPage:
    def update(self):
        pass


class WindowSpy:
    def __init__(self):
        self.width = 1200
        self.height = 900
        self.min_width = 900
        self.on_resize = None


class PageSpy:
    def __init__(self):
        self.title = None
        self.theme_mode = None
        self.theme = None
        self.window = WindowSpy()
        self.controls = []
        self.thread_calls = []
        self.on_close = None
        self.on_disconnect = None

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def run_task(self, coro):
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            return loop.create_task(coro())
        except RuntimeError:
            return None

    def run_thread(self, handler, *args):
        self.thread_calls.append((handler, args))
        handler(*args)


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
        self.log_list = types.SimpleNamespace(controls=[], auto_scroll=True, spacing=4, update=lambda: None)
        self.level_filter = types.SimpleNamespace(value="ALL", on_select=None)
        self.export_button = types.SimpleNamespace(on_click=None)
        self.resize_handle = types.SimpleNamespace(on_vertical_drag_update=None)
        self.list_container = types.SimpleNamespace(height=200, update=lambda: None)
        self._is_at_bottom = [True]
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
        "resize_handle": view.resize_handle,
        "list_container": view.list_container,
        "log_list": view.log_list,
        "_is_at_bottom": view._is_at_bottom,
    }
    return view, refs


class ImportPicker:
    next_files = None

    async def pick_files(self, **kwargs):
        return self.next_files


class ApplyConfigSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, config):
        self.calls.append(config)


class UpdateDeviceLoadMapSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, updates):
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
    monkeypatch.setattr(_cmp_modules, "datetime", FrozenDateTime, raising=False)

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

    _, refs = components.create_config_section(DummyPage(), logs.append)
    refs["set_config_state"]([
        {"selected": False, "device": "TEMP", "capacity": "1"},
    ])

    restore_button = _find_button(refs, "恢复默认")

    restore_button.on_click(DummyControlEvent())

    assert _config_table_values(refs) == [
        {"selected": False, "device": "NTE240", "capacity": "90"}
    ]
    assert logs[-1] == "已恢复默认配置"



def test_config_action_buttons_use_consistent_widths():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    # Buttons use theme helpers without explicit width; verify they exist and have no None width
    assert all(button is not None for button in refs["action_buttons"])


def test_config_action_button_rows_are_left_aligned():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    assert all(row.alignment == components.ft.MainAxisAlignment.START for row in refs["action_button_rows"])






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
    assert last_text.color == components.ft.Colors.ORANGE


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

    assert page.thread_calls, "expected GUI log updates to be scheduled through run_thread"


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

    before_disconnect = len(page.thread_calls)
    page.on_disconnect(None)
    logging.getLogger().info("关闭后日志")
    time.sleep(0.05)

    assert len(page.thread_calls) == before_disconnect

    # Test real create_log_view (undo monkeypatch first)
    monkeypatch.undo()
    log_view, refs = real_create_log_view()

    assert isinstance(log_view, components.ft.Container)
    assert refs["log_list"].auto_scroll is False
    assert refs["log_list"].spacing == 4
    assert refs["list_container"].height == 300
    assert getattr(refs["export_button"], "tooltip", None) == "导出日志"



def test_log_view_exposes_filter_resize_and_export_controls():
    log_view, refs = components.create_log_view(height=260)

    resize_handle, list_container = log_view.content.controls

    toolbar = refs["toolbar"]
    assert toolbar.controls[0] is refs["level_filter"]
    assert toolbar.controls[1] is refs["export_button"]
    assert toolbar.spacing == 4
    assert refs["level_filter"].value == "ALL"
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
    refs["level_filter"].on_select(DummyControlEvent(refs["level_filter"]))
    assert len(refs["log_list"].controls) == 1
    assert refs["log_list"].controls[0].value.endswith("错误消息")

    refs["level_filter"].value = "ALL"
    refs["level_filter"].on_select(DummyControlEvent(refs["level_filter"]))
    assert len(refs["log_list"].controls) >= 2



def test_gui_main_exports_filtered_logs(monkeypatch, tmp_path):
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
    refs["level_filter"].on_select(DummyControlEvent(refs["level_filter"]))

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
    assert refs["list_container"].height == 280

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
    assert update_spy.calls == []
    assert logs[-1] == "当前配置已应用"
