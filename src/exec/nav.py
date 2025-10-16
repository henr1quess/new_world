"""Automation helpers for navigating the in-game market UI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import keyboard
import win32api
import win32con
import win32gui
import yaml

from src.capture.calibrate import relative_rect
from src.capture.window import get_screen_resolution, get_window_rect, human_pause

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
CFG_CAPTURE = BASE / "config" / "capture.yaml"


def _load_ui_profile(ui_cfg_path: str) -> Dict[str, Any]:
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui_cfg = yaml.safe_load(fh) or {}
    profiles = ui_cfg.get("profiles") or {}
    if not profiles:
        raise ValueError("Nenhum profile definido em ui_profiles.yaml")
    return next(iter(profiles.values()))


def _load_capture_cfg() -> Dict[str, Any]:
    if CFG_CAPTURE.exists():
        with open(CFG_CAPTURE, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _focus_window() -> Dict[str, Any] | None:
    capture_cfg = _load_capture_cfg()
    title_hint = capture_cfg.get("window_title_contains")
    if not title_hint:
        logger.warning("window_title_contains não configurado em capture.yaml")
        return None

    win = get_window_rect(title_hint)
    if not win:
        logger.warning("janela com título contendo '%s' não encontrada", title_hint)
        return None

    hwnd = win.get("handle")
    if hwnd:
        try:
            win32gui.SetForegroundWindow(hwnd)
        except win32gui.error:
            logger.debug("não foi possível focar a janela alvo", exc_info=True)
    return win


def _click_at(x: int, y: int, pause_ms: int = 80) -> None:
    win32api.SetCursorPos((x, y))
    human_pause(pause_ms)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = rect
    return x + max(1, w) // 2, y + max(1, h) // 2


def open_item_by_search(ui_cfg_path: str, item_name: str) -> bool:
    """Focus the market window, search for an item and open the first result."""

    profile = _load_ui_profile(ui_cfg_path)
    search_cfg: Dict[str, Any] = profile.get("search", {})
    search_box = search_cfg.get("input")

    if not search_box:
        logger.error("Anchor 'search.input' não configurada no profile da UI")
        return False

    _focus_window()
    screen = get_screen_resolution()

    input_rect = relative_rect(search_box, screen)
    cx, cy = _rect_center(input_rect)

    _click_at(cx, cy, pause_ms=search_cfg.get("pause_before_focus_ms", 120))
    keyboard.send("ctrl+a")
    human_pause(search_cfg.get("pause_after_clear_ms", 80))

    delay = max(0.0, search_cfg.get("type_interval_ms", 30) / 1000.0)
    keyboard.write(item_name, delay=delay)

    submit_key = search_cfg.get("submit_key", "enter")
    if submit_key:
        human_pause(search_cfg.get("pause_before_submit_ms", 100))
        keyboard.send(submit_key)

    first_result = search_cfg.get("first_result")
    if first_result:
        result_rect = relative_rect(first_result, screen)
        rx, ry = _rect_center(result_rect)
        pause_ms = search_cfg.get("pause_before_result_click_ms", 180)
        _click_at(rx, ry, pause_ms=pause_ms)

    human_pause(search_cfg.get("pause_after_action_ms", 200))
    logger.debug("Item '%s' pesquisado via busca", item_name)
    return True
