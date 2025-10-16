import ctypes
import time
from typing import Dict, Optional, Tuple

from PIL import ImageGrab
import win32gui


def get_screen_resolution() -> Tuple[int, int]:
    """Return the current screen resolution as ``(width, height)``."""

    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_rect(x: int, y: int, w: int, h: int):
    """Capture a rectangular region of the screen specified in absolute pixels."""

    bbox = (x, y, x + w, y + h)
    return ImageGrab.grab(bbox=bbox)


def human_pause(ms: int = 120) -> None:
    """Pause execution for a short human-like delay expressed in milliseconds."""

    time.sleep(ms / 1000)


def _rect_to_xywh(rect: Tuple[int, int, int, int]) -> Dict[str, int]:
    """Convert a Windows rect tuple (left, top, right, bottom) into an ``x, y, w, h`` mapping."""

    left, top, right, bottom = rect
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def get_window_rect(title_contains: str) -> Optional[Dict[str, object]]:
    """Return the bounding box for the first visible window whose title contains the given text."""

    target = {"handle": None, "title": None, "rect": None}

    def enum_handler(hwnd, ctx):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if title_contains.lower() in title.lower():
            rect = win32gui.GetWindowRect(hwnd)
            ctx["handle"] = hwnd
            ctx["title"] = title
            ctx["rect"] = rect

    win32gui.EnumWindows(enum_handler, target)

    if target["rect"]:
        rect_xywh = _rect_to_xywh(target["rect"])
        return {
            "x": rect_xywh["x"],
            "y": rect_xywh["y"],
            "w": rect_xywh["w"],
            "h": rect_xywh["h"],
            "title": target["title"],
        }

    return None


def capture_rect_in_window(wx: int, wy: int, x: int, y: int, w: int, h: int):
    """Capture a rectangle relative to a window's top-left corner."""

    return capture_rect(wx + x, wy + y, w, h)
