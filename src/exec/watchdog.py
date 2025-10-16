"""Helpers to ensure the target game window is available."""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from src.capture.window import get_window_rect

_BASE_DIR = Path(__file__).resolve().parents[2]
_CAPTURE_CFG = _BASE_DIR / "config" / "capture.yaml"


def _load_title_hint() -> str:
    if not _CAPTURE_CFG.exists():
        return ""
    with open(_CAPTURE_CFG, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return (data.get("window_title_contains") or "").strip()


def wait_for_window(timeout_s: float = 5.0, poll_interval: float = 0.2) -> bool:
    """Poll until the game window is found or ``timeout_s`` is reached."""
    title_hint = _load_title_hint()
    if not title_hint:
        return False

    deadline = time.time() + max(0.0, timeout_s)
    while time.time() <= deadline:
        if get_window_rect(title_hint):
            return True
        time.sleep(max(0.01, poll_interval))
    return False


def assert_window_alive(raise_on_fail: bool = True, timeout_s: float = 2.0) -> bool:
    """Ensure the target window is alive, optionally raising on failure."""
    ok = wait_for_window(timeout_s=timeout_s)
    if not ok and raise_on_fail:
        raise RuntimeError("Janela do jogo não encontrada (perdeu foco ou crashou).")
    return ok
