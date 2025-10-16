import time
import ctypes
from typing import Tuple

from PIL import ImageGrab


def get_screen_resolution() -> Tuple[int, int]:
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_rect(x, y, w, h):
    """Capture a rectangular region of the screen specified in absolute pixels."""
    bbox = (x, y, x + w, y + h)
    return ImageGrab.grab(bbox=bbox)


def human_pause(ms: int = 120):
    time.sleep(ms / 1000)
