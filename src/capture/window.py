from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageGrab


def get_screen_resolution() -> Tuple[int, int]:
    """Return the size of the primary monitor."""
    try:
        bbox = ImageGrab.grab().getbbox()
        if bbox:
            return bbox[2], bbox[3]
        img = ImageGrab.grab()
        return img.size
    except Exception as exc:  # pragma: no cover - requires desktop environment
        raise RuntimeError("Screen capture is not available in this environment") from exc


def capture_rect(x: int, y: int, w: int, h: int) -> Image.Image:
    """Capture a rectangular region from the screen."""
    bbox = (x, y, x + w, y + h)
    try:
        return ImageGrab.grab(bbox=bbox)
    except Exception as exc:  # pragma: no cover - requires desktop environment
        raise RuntimeError("Screen capture is not available in this environment") from exc
