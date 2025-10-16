"""Automation helpers for navigating the in-game market UI."""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any, Dict, Tuple

import keyboard
import win32api
import win32con
import win32gui
import yaml

from src.capture.calibrate import relative_rect
from src.capture.window import (
    capture_rect,
    get_screen_resolution,
    get_window_rect,
    human_pause,
)
from src.ocr.engine import OCREngine, load_ocr_config

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]
CFG_CAPTURE = BASE / "config" / "capture.yaml"
CFG_OCR = BASE / "config" / "ocr.yaml"

_OCR_ENGINE: OCREngine | None = None


def _ensure_ocr_engine() -> OCREngine | None:
    global _OCR_ENGINE
    if _OCR_ENGINE:
        return _OCR_ENGINE
    if not CFG_OCR.exists():
        logger.debug("Arquivo de configuração OCR não encontrado: %s", CFG_OCR)
        return None
    try:
        cfg = load_ocr_config(str(CFG_OCR))
    except OSError:
        logger.exception("Falha ao carregar configuração OCR em %s", CFG_OCR)
        return None
    _OCR_ENGINE = OCREngine(cfg)
    return _OCR_ENGINE

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


def _screen_bounds() -> Tuple[int, int, int, int]:
    sw, sh = get_screen_resolution()
    return 0, 0, sw - 1, sh - 1


def _jitter_point(x: int, y: int, jitter_px: int, bounds: Tuple[int, int, int, int]) -> tuple[int, int]:
    if jitter_px <= 0:
        return x, y
    left, top, right, bottom = bounds
    jx = max(left, min(right, x + random.randint(-jitter_px, jitter_px)))
    jy = max(top, min(bottom, y + random.randint(-jitter_px, jitter_px)))
    return jx, jy


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


def _click_at(
    x: int,
    y: int,
    pause_ms: int = 80,
    jitter_px: int = 0,
    bounds: Tuple[int, int, int, int] | None = None,
) -> None:
    bounds = bounds or _screen_bounds()
    jx, jy = _jitter_point(x, y, jitter_px=jitter_px, bounds=bounds)
    win32api.SetCursorPos((jx, jy))
    human_pause(pause_ms)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = rect
    return x + max(1, w) // 2, y + max(1, h) // 2


def _confirm_first_result(
    first_result_cfg: Dict[str, Any],
    screen: tuple[int, int],
    expected_name: str,
    *,
    min_conf: float,
) -> bool:
    engine = _ensure_ocr_engine()
    if not engine:
        logger.debug("OCR indisponível para confirmação de resultados")
        return True

    rx, ry, rw, rh = relative_rect(first_result_cfg, screen)
    snapshot = capture_rect(rx, ry, rw, rh)
    text, conf = engine.text_and_conf(snapshot)
    norm_text = " ".join(text.split()).lower()
    expected_head = expected_name.strip().split()
    expected_token = expected_head[0].lower() if expected_head else ""

    if conf < min_conf:
        logger.warning(
            "Confiança %.2f abaixo do mínimo %.2f para confirmação de '%s' (texto lido: '%s')",
            conf,
            min_conf,
            expected_name,
            text,
        )
        return False

    if expected_token and expected_token not in norm_text:
        logger.warning(
            "Primeira palavra '%s' não encontrada no resultado OCR '%s'",
            expected_token,
            text,
        )
        return False

    logger.debug("Confirmação OCR bem sucedida para '%s' (texto: '%s')", expected_name, text)
    return True


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
    bounds = (0, 0, screen[0] - 1, screen[1] - 1)
    jitter_px = int(search_cfg.get("click_jitter_px", 4))

    input_rect = relative_rect(search_box, screen)
    cx, cy = _rect_center(input_rect)

    _click_at(
        cx,
        cy,
        pause_ms=search_cfg.get("pause_before_focus_ms", 120),
        jitter_px=jitter_px,
        bounds=bounds,
    )
    keyboard.send("ctrl+a")
    human_pause(search_cfg.get("pause_after_clear_ms", 80))

    delay = max(0.0, search_cfg.get("type_interval_ms", 30) / 1000.0)
    keyboard.write(item_name, delay=delay)

    submit_key = search_cfg.get("submit_key", "enter")
    if submit_key:
        human_pause(search_cfg.get("pause_before_submit_ms", 100))
        keyboard.send(submit_key)

    first_result = search_cfg.get("first_result")
    confirmed = True
    pause_before_confirm_ms = search_cfg.get("pause_before_confirm_ms", 220)
    confirm_min_conf = float(search_cfg.get("confirm_min_conf", 0.55))

    if first_result:
        result_rect = relative_rect(first_result, screen)
        rx, ry = _rect_center(result_rect)
        pause_ms = search_cfg.get("pause_before_result_click_ms", 180)
        _click_at(rx, ry, pause_ms=pause_ms, jitter_px=jitter_px, bounds=bounds)

        if search_cfg.get("confirm_first_result", True):
            human_pause(pause_before_confirm_ms)
            confirmed = _confirm_first_result(first_result, screen, item_name, min_conf=confirm_min_conf)

    human_pause(search_cfg.get("pause_after_action_ms", 200))
    logger.debug("Item '%s' pesquisado via busca", item_name)
    return confirmed
