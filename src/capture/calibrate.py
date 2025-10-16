from __future__ import annotations

from typing import Iterable, Tuple


def relative_rect(rect: Iterable[float], screen: Tuple[int, int]) -> Tuple[int, int, int, int]:
    """Converte coordenadas relativas (0-1) para pixels absolutos."""
    sx, sy = screen
    rx, ry, rw, rh = rect
    return int(rx * sx), int(ry * sy), int(rw * sx), int(rh * sy)
