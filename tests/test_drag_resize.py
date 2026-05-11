"""Test that the drag resize handler uses the correct DragUpdateEvent attribute."""
import dataclasses
import flet as ft


def test_drag_update_event_has_primary_delta():
    """DragUpdateEvent should have primary_delta (incremental vertical delta)."""
    fields = {f.name for f in dataclasses.fields(ft.DragUpdateEvent)}
    assert "primary_delta" in fields, "DragUpdateEvent missing primary_delta"


def test_drag_update_event_has_no_delta_y():
    """DragUpdateEvent should NOT have delta_y (this was the bug)."""
    fields = {f.name for f in dataclasses.fields(ft.DragUpdateEvent)}
    assert "delta_y" not in fields, "DragUpdateEvent unexpectedly has delta_y"


def test_resize_handler_uses_primary_delta():
    """The drag handler must read e.primary_delta, not e.delta_y."""
    import inspect
    source = inspect.getsource(__import__("gui.main", fromlist=["main"]))
    assert "e.primary_delta" in source, "Handler should use e.primary_delta"
    assert "e.delta_y" not in source, "Handler should not use e.delta_y"


def test_tab_height_adjusted_on_resize():
    """When log height changes, tab content height must shrink to keep total within page."""
    import inspect
    source = inspect.getsource(__import__("gui.main", fromlist=["main"]))
    # The resize handler must update tab content height, not just log height
    assert "tab_content_col.height" in source, (
        "Resize handler must adjust tab_content_col.height to prevent log overflow"
    )

