"""user_config 组件测试"""
import json
import pathlib
import sys

import pytest
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from func import config_loader

import flet as ft


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

# 复用 test_gui_components.py 中的最小 Spy
from tests.test_gui_components import DummyPage, PageSpy, DummyControlEvent

# 确保 gui 包可导入
if "gui" not in sys.modules:
    gui_pkg = types.ModuleType("gui")
    gui_pkg.__path__ = [str(ROOT / "gui")]
    gui_pkg.__package__ = "gui"
    sys.modules["gui"] = gui_pkg

import importlib.util
spec = importlib.util.spec_from_file_location(
    "gui.components",
    ROOT / "gui" / "components" / "__init__.py",
    submodule_search_locations=[str(ROOT / "gui" / "components")],
)
components = importlib.util.module_from_spec(spec)
sys.modules["gui.components"] = components
spec.loader.exec_module(components)


@pytest.fixture(autouse=True)
def _reset_runtime_config():
    config_loader._runtime_config = None
    yield
    config_loader._runtime_config = None


def test_user_config_section_contains_expected_action_buttons():
    _, refs = components.create_user_config_section(DummyPage(), lambda message: None)

    assert _find_button(refs, "保存数据库配置") is not None
    assert _find_button(refs, "重新加载") is not None
    assert _find_button(refs, "恢复默认") is not None


def test_user_config_save_persists_database_section(monkeypatch, tmp_path):
    logs = []
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)

    page = PageSpy()
    _, refs = components.create_user_config_section(page, logs.append)

    refs["db_type"].value = "mysql"
    refs["db_host"].value = "127.0.0.1"
    refs["db_port"].value = "5432"
    refs["db_name"].value = "mining"
    refs["db_user"].value = "admin"
    refs["db_password"].value = "secret"

    refs["save_database_config"](DummyControlEvent())

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["user_config"]["database"]["db_port"] == 5432
    assert saved["user_config"]["database"]["db_host"] == "127.0.0.1"
    assert logs[-1] == "已保存数据库连接配置"


def test_user_config_invalid_port_shows_error(monkeypatch, tmp_path):
    logs = []
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)

    _, refs = components.create_user_config_section(PageSpy(), logs.append)
    refs["db_port"].value = "99999"

    refs["save_database_config"](DummyControlEvent())

    assert refs["db_port"].error_text == "端口必须在 0-65535 之间"
    assert logs[-1] == "保存数据库配置失败：端口不合法"
