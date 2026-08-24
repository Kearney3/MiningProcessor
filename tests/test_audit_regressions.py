"""Regression tests for findings confirmed in the 2026-08-24 audit."""

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from func import config_loader
from func import ledger_match
from func.sync import sync_engines
from func.sync.api_client import MineBaseAPIClient
from func.sync.db_client import MineBaseDBClient
from gui import logic
import tauri_bridge


def test_load_config_returns_an_independent_deep_copy(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"nested": {"list": [1], "mapping": {"keep": True}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    config_loader._invalidate_config_cache()

    loaded = config_loader.load_config()
    loaded["nested"]["list"].append(2)
    loaded["nested"]["mapping"]["changed"] = True

    fresh = config_loader.load_config()
    assert fresh["nested"] == {"list": [1], "mapping": {"keep": True}}


def test_deep_merge_does_not_share_unoverridden_children():
    merged = config_loader._deep_merge(
        {"nested": {"list": [1], "mapping": {"keep": True}}},
        {},
    )
    merged["nested"]["list"].append(2)
    merged["nested"]["mapping"]["changed"] = True

    assert merged == {
        "nested": {"list": [1, 2], "mapping": {"keep": True, "changed": True}},
    }
    # The assertion must inspect a separately-created base so the test catches
    # sharing rather than merely validating the mutated result.
    base = {"nested": {"list": [1], "mapping": {"keep": True}}}
    copied = config_loader._deep_merge(base, {})
    copied["nested"]["list"].append(2)
    copied["nested"]["mapping"]["changed"] = True
    assert base == {"nested": {"list": [1], "mapping": {"keep": True}}}


def test_device_load_map_read_modify_write_is_serialized(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"device_load_map": {}}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    config_loader._invalidate_config_cache()

    original_load = config_loader._load_json
    state = {"active": 0, "max_active": 0}
    state_lock = threading.Lock()

    def monitored_load(path):
        if path == config_file:
            with state_lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.01)
            try:
                return original_load(path)
            finally:
                with state_lock:
                    state["active"] -= 1
        return original_load(path)

    monkeypatch.setattr(config_loader, "_load_json", monitored_load)
    threads = [
        threading.Thread(target=config_loader.update_device_load_map, args=({f"D{i}": i},))
        for i in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["max_active"] == 1
    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["device_load_map"] == {"D0": 0, "D1": 1}


@pytest.mark.parametrize(
    ("handler", "params"),
    [
        (tauri_bridge._process_worktime, {"path": str(Path.cwd() / "config.json")}),
        (tauri_bridge._save_config, {}),
        (tauri_bridge._save_minebase_config, {}),
        (tauri_bridge._update_device_load_map, {}),
        (tauri_bridge._apply_device_load_map, {}),
        (tauri_bridge._set_load_map_version, {}),
        (tauri_bridge._update_maintenance_classifications, {}),
        (tauri_bridge._save_minebase_column_mapping, {}),
        (tauri_bridge._read_excel_sheet, {"path": str(Path.cwd() / "config.json")}),
    ],
)
def test_tauri_rpc_missing_required_parameters_are_validation_errors(handler, params):
    with pytest.raises(ValueError, match="Missing required parameter"):
        handler(params)


def test_path_sanitizer_rejects_null_bytes():
    from func.path_utils import sanitize_path

    with pytest.raises(ValueError, match="null bytes"):
        sanitize_path("report\x00.xlsx")


def test_write_text_file_rejects_oversized_content(tmp_path):
    with pytest.raises(ValueError, match="byte limit"):
        tauri_bridge._write_text_file({
            "path": str(tmp_path / "log.txt"),
            "content": "x" * (tauri_bridge.MAX_TEXT_FILE_BYTES + 1),
        })


def test_url_validation_rejects_private_dns_results():
    with patch("tauri_bridge.socket.getaddrinfo", return_value=[
        (0, 0, 0, "", ("10.0.0.8", 0)),
    ]):
        with pytest.raises(ValueError, match="private or local"):
            tauri_bridge._validate_url("https://internal.example")


class _RecordingCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.connection.calls.append((query, params))

    def fetchone(self):
        return None


class _RecordingConnection:
    def __init__(self):
        self.calls = []

    def cursor(self):
        return _RecordingCursor(self)


def test_resolve_equipment_id_escapes_like_wildcards():
    client = object.__new__(MineBaseDBClient)
    client.conn = _RecordingConnection()

    assert client.resolve_equipment_id("Model_X%") is None

    query, params = client.conn.calls[-1]
    assert "ESCAPE" in query
    assert params == (r"%Model\_X\%%",)


def test_api_client_retries_transient_network_failure():
    import urllib.error

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok": true}'

    client = MineBaseAPIClient("https://example.test", "user", "password")
    with patch(
        "urllib.request.urlopen",
        side_effect=[urllib.error.URLError("temporary"), Response()],
    ) as urlopen, patch("time.sleep") as sleep:
        assert client._request("GET", "/health") == {"ok": True}

    assert urlopen.call_count == 2
    sleep.assert_called_once()


def test_db_client_uses_connection_timeout_and_context_cleanup():
    pytest.importorskip("psycopg2")
    connection = SimpleNamespace(closed=False, autocommit=None)
    connection.close = lambda: setattr(connection, "closed", True)
    connection.rollback = lambda: setattr(connection, "rolled_back", True)
    with patch("psycopg2.connect", return_value=connection) as connect:
        from func.sync.db_client import DB_CONNECT_TIMEOUT_SECONDS

        with MineBaseDBClient("host", 5432, "db", "user", "password") as client:
            assert client.conn is connection

    assert connect.call_args.kwargs["connect_timeout"] == DB_CONNECT_TIMEOUT_SECONDS
    assert connection.closed is True


def test_user_config_file_is_saved_with_private_permissions(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("Windows does not expose POSIX file mode semantics")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", tmp_path / "config.json")
    user_file = tmp_path / "config.user.json"
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)
    config_loader.save_user_config({"secret": "value"})

    assert (user_file.stat().st_mode & 0o777) == 0o600


def test_update_llm_config_does_not_mutate_caller_payload(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", tmp_path / "config.user.json")
    config_loader._invalidate_config_cache()

    updates = {"api_key": "", "model": "local-model"}
    config_loader.update_llm_config(updates)

    assert updates == {"api_key": "", "model": "local-model"}


def test_update_llm_config_preserves_saved_key_when_masked_value_is_empty(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")
    user_file = tmp_path / "config.user.json"
    user_file.write_text(
        json.dumps({"user_config": {"llm_labeling": {"api_key": "keychain", "model": "old"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(config_loader, "_USER_CONFIG_FILE", user_file)
    config_loader._invalidate_config_cache()

    config_loader.update_llm_config({"api_key": "", "model": "new"})
    saved = json.loads(user_file.read_text(encoding="utf-8"))

    assert saved["user_config"]["llm_labeling"] == {"api_key": "keychain", "model": "new"}


class _PartialCommitDB:
    def __init__(self):
        self.pending = []
        self.committed = []
        self.poisoned = False
        self.commit_count = 0
        self.rollback_count = 0

    def check_duplicate(self, *_args):
        return False

    def insert_rows(self, _table, _columns, values_list):
        value = values_list[0][0]
        if value == 2:
            self.poisoned = True
            raise RuntimeError("bad row")
        if self.poisoned:
            raise RuntimeError("current transaction is aborted")
        self.pending.append(value)

    def commit(self):
        self.commit_count += 1
        if self.poisoned:
            raise RuntimeError("commit failed")
        self.committed.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.rollback_count += 1
        self.pending.clear()
        self.poisoned = False


def test_sync_via_db_keeps_successful_rows_when_one_row_fails():
    db = _PartialCommitDB()
    rows = [{"id": 1}, {"id": 2}, {"id": 3}]

    def resolve(_data_type, row, _db_client, **_kwargs):
        return row

    def map_row(row):
        return ["value"], [row["id"]]

    with patch.object(sync_engines, "_resolve_fks_for_db", side_effect=resolve), \
         patch.object(sync_engines, "_map_row_to_db_columns", side_effect=map_row):
        result = sync_engines.sync_via_db("fuel", rows, {}, db)

    assert result["success"] == 2
    assert result["failed"] == 1
    assert db.committed == [1, 3]
    assert db.pending == []
    assert db.commit_count == 2
    assert db.rollback_count == 1


def test_match_sheet_passes_id_to_excavator_matching():
    calls = []

    class Ledger:
        def match_device(self, name=None, device_id=None):
            calls.append((name, device_id))
            return {
                "标准设备名称": name or "",
                "标准设备编号": device_id or "",
                "标准公司名称": "测试公司",
            }

    frame = pd.DataFrame({
        "矿卡名称": ["TRUCK"],
        "挖机名称": ["EXCAVATOR"],
        "设备编号": ["ID-7"],
    })

    ledger_match.match_sheet(frame, Ledger(), None, "矿卡名称", "设备编号", None)

    assert calls == [("TRUCK", "ID-7"), ("EXCAVATOR", "ID-7")]


def test_module_labels_follow_language_changes():
    from gui import i18n

    i18n.init("zh")
    i18n.set_language("en")
    assert logic._module_label("merge") == "File Merge"
    i18n.init("zh")


def test_language_change_dialog_uses_dialog_lifecycle():
    import importlib

    main = importlib.import_module("gui.main")
    from gui import i18n

    class Page:
        def __init__(self):
            self.overlay = []
            self.shown = []
            self.popped = 0

        def show_dialog(self, dialog):
            self.shown.append(dialog)

        def pop_dialog(self):
            self.popped += 1

        def update(self):
            pass

    i18n.init("zh")
    page = Page()
    switcher = main._create_lang_switcher(page)
    with patch.object(main, "update_user_config"):
        switcher.content.on_change(SimpleNamespace(data="en"))

    assert len(page.shown) == 1
    page.shown[0].actions[0].on_click(None)
    assert page.popped == 1
    i18n.init("zh")


def test_log_system_chains_and_restores_existing_resize_handler():
    from gui.log_system import LogSystem

    class Control:
        def __init__(self, value=None, height=None):
            self.value = value
            self.height = height
            self.data = {}
            self.on_click = None
            self.on_select = None
            self.on_scroll = None
            self.on_vertical_drag_start = None
            self.on_vertical_drag_update = None

        def update(self):
            pass

    class Page:
        def __init__(self):
            self.services = []
            self.height = 800
            self.window = SimpleNamespace(height=800, on_resize=None)

        def run_task(self, *_args, **_kwargs):
            return None

    refs = {
        key: Control(height=300 if key == "list_container" else None)
        for key in (
            "log_list", "list_container", "level_filter", "export_button",
            "resize_handle", "clear_button", "scroll_bottom_button",
            "follow_status", "count_text",
        )
    }
    page = Page()
    calls = []
    previous = lambda event: calls.append(event)
    page.window.on_resize = previous
    system = LogSystem(page, refs)
    system.start()
    page.window.on_resize("resize")
    assert calls == ["resize"]
    system.shutdown()
    assert page.window.on_resize == previous


class _DialogPage:
    def show_dialog(self, dialog):
        # Simulate the user selecting Continue immediately.
        dialog.actions[0].on_click(None)

    def pop_dialog(self):
        pass


def test_batch_process_missing_file_confirmation_does_not_raise_name_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        logic,
        "scan_files",
        lambda _path: ({"fuel": ["Fuel.xlsx"]}, ["production"]),
    )
    monkeypatch.setattr(
        logic,
        "process_files",
        lambda *_args, **_kwargs: ({"fuel": {"油耗信息": None}}, {}),
    )
    monkeypatch.setattr(logic, "set_btn_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(logic, "_show_batch_progress", lambda *_args: None)
    monkeypatch.setattr(logic, "_hide_batch_progress", lambda *_args: None)
    monkeypatch.setattr(logic, "_show_snackbar", lambda *_args, **_kwargs: None)

    refs = {
        "path": SimpleNamespace(value=str(tmp_path)),
        "year": SimpleNamespace(value="2025"),
        "month": SimpleNamespace(value="1"),
        "auto_detect": SimpleNamespace(value=True),
        "merge": SimpleNamespace(value=False),
        "btn": object(),
    }

    asyncio.run(logic.on_batch_process(_DialogPage(), refs, lambda *_args, **_kwargs: None))
