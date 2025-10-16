from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
import win32api
import win32con
import win32gui

from .calibrate import relative_rect
from .window import get_window_rect, human_pause


BASE = Path(__file__).resolve().parents[2]
CFG_CAPTURE = BASE / "config" / "capture.yaml"


def _load_ui_profile(ui_cfg_path: str) -> Dict[str, Any]:
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui_cfg = yaml.safe_load(fh)
    return next(iter(ui_cfg["profiles"].values()))


def _load_capture_cfg() -> Dict[str, Any]:
    if CFG_CAPTURE.exists():
        with open(CFG_CAPTURE, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _focus_window() -> Dict[str, Any] | None:
    capture_cfg = _load_capture_cfg()
    title_hint = capture_cfg.get("window_title_contains")
    if not title_hint:
        return None

    win = get_window_rect(title_hint)
    if not win:
        return None

    hwnd = win.get("handle")
    if hwnd:
        try:
            win32gui.SetForegroundWindow(hwnd)
        except win32gui.error:
            # If the window cannot be focused, continue without raising.
            pass
    return win


def focus_and_scroll(ui_cfg_path: str, anchor_name: str = "list_zone") -> None:
    """Bring the target window to the foreground and scroll once using the provided anchor."""

    profile = _load_ui_profile(ui_cfg_path)
    scroll_cfg: Dict[str, Any] = profile.get(
        "buy_panel_scroll" if anchor_name == "buy_panel_zone" else "scroll", {}
    )

    win = _focus_window()
    if win is None:
        return

    base = (win["w"], win["h"])
    x, y, w, h = relative_rect(profile["anchors"][anchor_name], base)

    cx = win["x"] + x + w // 2
    cy = win["y"] + y + min(h - 1, int(0.5 * h))

    win32api.SetCursorPos((cx, cy))
    human_pause(scroll_cfg.get("pause_before_scroll_ms", 80))

    step_pixels = scroll_cfg.get("step_pixels", 240)
    wheel_steps = max(1, int(round(step_pixels / 120.0)))
    wheel_delta = -wheel_steps * win32con.WHEEL_DELTA
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)

    pause_ms = scroll_cfg.get("pause_ms", 150)
    human_pause(pause_ms)


def focus_and_scroll_one_page(ui_cfg_path: str) -> None:
    """Compat wrapper that scrolls the default list zone."""

    focus_and_scroll(ui_cfg_path, anchor_name="list_zone")
