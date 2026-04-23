import importlib.util
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


class FrozenDateTime:
    @classmethod
    def now(cls):
        return types.SimpleNamespace(year=2026, month=4)


def _row_values(rows):
    return [
        (row.cells[0].content.value, row.cells[1].content.value)
        for row in rows
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


def test_delete_selected_uses_helper_refs_to_remove_only_checked_rows():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["append_row"]("TR100", 35)
    refs["append_row"]("EH4000", 85)
    refs["append_row"]("NTE240", 85)
    refs["config_rows"][0].selected = True
    refs["config_rows"][2].selected = True

    refs["remove_selected_rows"]()

    assert _row_values(refs["config_rows"]) == [("EH4000", "85")]


def test_delete_selected_leaves_unchecked_rows_unchanged():
    _, refs = components.create_config_section(DummyPage(), lambda message: None)

    refs["append_row"]("TR100", 35)
    refs["append_row"]("EH4000", 85)
    refs["append_row"]("NTE240", 85)
    before_unchecked = _row_values(refs["config_rows"])[1:]
    refs["config_rows"][0].selected = True

    refs["remove_selected_rows"]()

    assert _row_values(refs["config_rows"]) == before_unchecked
