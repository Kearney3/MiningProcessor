import importlib.util
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "gui_components_under_test", ROOT / "gui" / "components.py"
)
components = importlib.util.module_from_spec(spec)
spec.loader.exec_module(components)


class DummyPage:
    def update(self):
        pass


class DummyCheckbox:
    def __init__(self, value):
        self.value = value


class FrozenDateTime:
    @classmethod
    def now(cls):
        return types.SimpleNamespace(year=2026, month=4)


def _config_table_values(refs):
    return [
        {
            "selected": row["selected"],
            "device": row["device"],
            "capacity": str(row["capacity"]),
        }
        for row in refs["config_state"]
    ]


def test_work_module_exposes_year_month_refs_with_current_date_defaults(monkeypatch):
    monkeypatch.setattr(components, "datetime", FrozenDateTime, raising=False)

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
