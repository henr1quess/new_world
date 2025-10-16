from pathlib import Path
import time
import yaml
import pyautogui as pg

from .calibrate import relative_rect
from .window import get_screen_resolution, get_window_rect


def _center_of(rect):
    x, y, w, h = rect
    return x + w // 2, y + h // 2


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def focus_and_scroll_one_page(ui_cfg_path: str, pixels: int | None = None, pause_ms: int | None = None) -> None:
    """
    Clica no centro da list_zone e executa scroll para baixo.
    - 'pixels' e 'pause_ms' são sobrescritos pelos valores do UI profile se existirem.
    """
    ui_cfg = _load_yaml(Path(ui_cfg_path))
    profiles = ui_cfg.get("profiles") or {}
    if not profiles:
        raise ValueError("UI config must contain at least one profile")

    prof = next(iter(profiles.values()))
    anchors = prof.get("anchors") or {}
    if "list_zone" not in anchors:
        raise ValueError("Profile must define a 'list_zone' anchor")

    list_anchor = anchors["list_zone"]
    scroll_cfg = prof.get("scroll") or {}
    step_px = scroll_cfg.get("step_pixels", pixels if pixels is not None else 240)
    pause_ms_value = scroll_cfg.get("pause_ms", pause_ms if pause_ms is not None else 150)

    # Janela alvo a partir de config/capture.yaml (se disponível)
    cap_cfg_path = Path(__file__).resolve().parents[2] / "config" / "capture.yaml"
    cap_cfg = _load_yaml(cap_cfg_path)
    title_sub = (cap_cfg.get("window_title_contains") or "").strip()
    wnd = get_window_rect(title_sub) if title_sub else None

    if wnd:
        base_size = (wnd["w"], wnd["h"])
        list_rect = relative_rect(list_anchor, base_size)
        cx, cy = _center_of(list_rect)
        ax, ay = wnd["x"] + cx, wnd["y"] + cy
    else:
        base_size = get_screen_resolution()
        list_rect = relative_rect(list_anchor, base_size)
        ax, ay = _center_of(list_rect)

    # Focar list_zone e rolar
    pg.moveTo(ax, ay, duration=0.05)
    pg.click()

    if step_px == 0:
        time.sleep(pause_ms_value / 1000)
        return

    # Aproximação: ~120px ≈ 1 notch. pyautogui.scroll usa "notches".
    notches = max(1, int(abs(step_px) / 120))
    direction = -1 if step_px >= 0 else 1
    pg.scroll(direction * notches)
    time.sleep(pause_ms_value / 1000)
