import time
import ctypes
from ctypes import wintypes
from typing import Dict, Optional, Tuple

from PIL import ImageGrab


def get_screen_resolution() -> Tuple[int, int]:
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_rect(x, y, w, h):
    """Capture a rectangular region of the screen specified in absolute pixels."""
    bbox = (x, y, x + w, y + h)
    return ImageGrab.grab(bbox=bbox)


def get_window_rect(title_contains: str) -> Optional[Dict[str, int]]:
    """Return the bounding rect of the first visible window whose title contains the substring."""

    user32 = ctypes.windll.user32

    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)  # type: ignore[attr-defined]
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowTextW = user32.GetWindowTextW
    GetWindowRect = user32.GetWindowRect

    results: Dict[str, int] = {}

    def callback(hwnd, _lparam):
        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLengthW(hwnd)
        if not length:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value

        if title_contains.lower() not in title.lower():
            return True

        rect = wintypes.RECT()  # type: ignore[attr-defined]
        if not GetWindowRect(hwnd, ctypes.byref(rect)):
            return True

        results.update({
            "x": rect.left,
            "y": rect.top,
            "w": rect.right - rect.left,
            "h": rect.bottom - rect.top,
        })
        return False  # stop enumeration

    EnumWindows(EnumWindowsProc(callback), 0)

    return results or None


def capture_rect_in_window(wx: int, wy: int, x: int, y: int, w: int, h: int):
    """Capture a rectangle using coordinates relative to the top-left of a window."""

    return capture_rect(wx + x, wy + y, w, h)


def human_pause(ms: int = 120):
    time.sleep(ms / 1000)
