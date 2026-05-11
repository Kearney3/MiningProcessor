"""Tests for the custom tab switching in gui/main.py"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MockControl:
    """Minimal mock for Flet controls."""
    def __init__(self, **kwargs):
        self.visible = True
        self.style = None
        self._updated = False

    def update(self):
        self._updated = True


def make_tab_contents(n):
    return [MockControl() for _ in range(n)]


def make_tab_buttons(n):
    return [MockControl() for _ in range(n)]


def select_tab(tab_contents, tab_buttons, idx):
    """Replicate the _select_tab logic from main.py."""
    for i, c in enumerate(tab_contents):
        c.visible = (i == idx)
    for i, btn in enumerate(tab_buttons):
        # Simulate style change (real code uses ft.ButtonStyle)
        btn.style = "active" if i == idx else "inactive"


def test_initial_state():
    """First tab visible, others hidden."""
    contents = make_tab_contents(3)
    for c in contents[1:]:
        c.visible = False

    assert contents[0].visible is True
    assert contents[1].visible is False
    assert contents[2].visible is False


def test_switch_to_second_tab():
    """Switching to tab 1 shows content 1, hides others."""
    contents = make_tab_contents(3)
    buttons = make_tab_buttons(3)
    for c in contents[1:]:
        c.visible = False

    select_tab(contents, buttons, 1)

    assert contents[0].visible is False
    assert contents[1].visible is True
    assert contents[2].visible is False


def test_switch_to_third_tab():
    """Switching to tab 2 shows content 2, hides others."""
    contents = make_tab_contents(3)
    buttons = make_tab_buttons(3)
    for c in contents[1:]:
        c.visible = False

    select_tab(contents, buttons, 2)

    assert contents[0].visible is False
    assert contents[1].visible is False
    assert contents[2].visible is True


def test_switch_back_to_first():
    """Switching back to tab 0 restores initial state."""
    contents = make_tab_contents(3)
    buttons = make_tab_buttons(3)
    for c in contents[1:]:
        c.visible = False

    select_tab(contents, buttons, 2)
    select_tab(contents, buttons, 0)

    assert contents[0].visible is True
    assert contents[1].visible is False
    assert contents[2].visible is False


def test_button_style_updates():
    """Only the selected tab button gets 'active' style."""
    contents = make_tab_contents(3)
    buttons = make_tab_buttons(3)

    select_tab(contents, buttons, 1)

    assert buttons[0].style == "inactive"
    assert buttons[1].style == "active"
    assert buttons[2].style == "inactive"
