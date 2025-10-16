"""Helpers for interacting with the in-game market UI via anchors."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import time

import pyautogui as pg
import yaml

from ..capture.calibrate import relative_rect
from ..capture.window import get_screen_resolution, get_window_rect

BASE_DIR = Path(__file__).resolve().parents[2]
CFG_CAPTURE = BASE_DIR / "config" / "capture.yaml"


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _base_and_window() -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Return the base resolution and window origin for the configured capture target."""

    capture_cfg = _load_yaml(CFG_CAPTURE) if CFG_CAPTURE.exists() else {}
    title_sub = (capture_cfg.get("window_title_contains") or "").strip()
    window_info = get_window_rect(title_sub) if title_sub else None
    if window_info:
        base_size = (window_info["w"], window_info["h"])
        origin = (window_info["x"], window_info["y"])
    else:
        base_size = get_screen_resolution()
        origin = (0, 0)
    return base_size, origin


def _anchor_center(ui_cfg_path: str, anchor_name: str) -> Tuple[int, int]:
    """Return the absolute pixel coordinates for the centre of the given anchor."""

    ui_cfg = _load_yaml(Path(ui_cfg_path))
    profile = next(iter(ui_cfg["profiles"].values()))
    anchors = profile["anchors"]
    if anchor_name not in anchors:
        raise RuntimeError(f"Anchor '{anchor_name}' não encontrado no ui_profiles.yaml")

    base, origin = _base_and_window()
    x, y, w, h = relative_rect(anchors[anchor_name], base)
    ax = origin[0] + x + w // 2
    ay = origin[1] + y + h // 2
    return ax, ay


def click_anchor(ui_cfg_path: str, anchor_name: str, delay_ms: int = 120) -> None:
    """Move the cursor to the given anchor and perform a click with a short delay."""

    ax, ay = _anchor_center(ui_cfg_path, anchor_name)
    pg.moveTo(ax, ay, duration=0.05)
    pg.click()
    time.sleep(max(0, delay_ms) / 1000)


def type_in_search(ui_cfg_path: str, text: str, press_enter: bool = False) -> None:
    """Focus the configured search box, type text and optionally confirm with Enter."""

    click_anchor(ui_cfg_path, "search_box")
    pg.hotkey("ctrl", "a")
    time.sleep(0.05)
    pg.press("backspace")
    time.sleep(0.05)
    if text:
        pg.write(text, interval=0.02)
    time.sleep(0.3)
    if press_enter:
        pg.press("enter")
        time.sleep(0.3)
    else:
        try:
            click_anchor(ui_cfg_path, "results_zone", delay_ms=120)
        except RuntimeError:
            # Results zone may be optional depending on the game behaviour.
            pass


def open_item_by_search(ui_cfg_path: str, item_name: str) -> None:
    """Search for an item in the market UI and open its results list."""

    type_in_search(ui_cfg_path, item_name, press_enter=False)
