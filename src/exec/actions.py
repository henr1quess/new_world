from pathlib import Path
import time
import yaml

from ..capture.window import (
    capture_rect,
    capture_rect_in_window,
    get_screen_resolution,
    get_window_rect,
)
from ..capture.calibrate import relative_rect
from ..ocr.engine import OCREngine, load_ocr_config
from ..utils.timing import sleep_ms


def _capture_fn():
    with open(
        Path(__file__).resolve().parents[2] / "config" / "capture.yaml",
        "r",
        encoding="utf-8",
    ) as fh:
        cap_cfg = yaml.safe_load(fh)

    title = (cap_cfg.get("window_title_contains") or "").strip()
    wnd = get_window_rect(title) if title else None
    if wnd:
        base = (wnd["w"], wnd["h"])

        def cap(x, y, w, h):
            return capture_rect_in_window(wnd["x"], wnd["y"], x, y, w, h)

        return base, cap
    base = get_screen_resolution()

    def cap(x, y, w, h):
        return capture_rect(x, y, w, h)

    return base, cap


def ocr_first_row_name(ui_cfg_path: str, ocr_cfg_path: str) -> str:
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui = yaml.safe_load(fh)

    prof = next(iter(ui["profiles"].values()))
    cols = prof["columns"]
    base, cap = _capture_fn()
    lx, ly, lw, lh = relative_rect(prof["anchors"]["list_zone"], base)
    line_h = int(lh / 12)
    y0 = ly
    name_rect = (
        lx + int(cols["name"]["x"] * lw),
        y0,
        int(cols["name"]["w"] * lw),
        line_h,
    )
    eng = OCREngine(load_ocr_config(ocr_cfg_path))
    txt, _ = eng.text_and_conf(cap(*name_rect))
    return " ".join(txt.split())


def wait_for_item_visible(
    ui_cfg_path: str,
    ocr_cfg_path: str,
    expected_substr: str,
    timeout_s: float = 3.0,
) -> bool:
    t0 = time.time()
    exp = expected_substr.lower()
    while time.time() - t0 < timeout_s:
        txt = (ocr_first_row_name(ui_cfg_path, ocr_cfg_path) or "").lower()
        if exp and exp in txt:
            return True
        sleep_ms(150, jitter=0.3)
    return False


# ----- Esqueleto de ações de domínio (a implementar no Nível 2) -----

def place_buy_order(ui_cfg_path: str, ocr_cfg_path: str, price: float, qty: int) -> bool:
    """
    TODO: clicar no botão 'Buy', preencher campos, confirmar e validar feedback.
    Retorna True/False conforme confirmação visual por OCR/âncora.
    """
    # Aqui entrarão cliques em âncoras 'buy_button', 'price_input', 'qty_input', 'confirm_button'
    # e verificação de um anchor/label de sucesso.
    return False


def place_sell_order(ui_cfg_path: str, ocr_cfg_path: str, price: float, qty: int) -> bool:
    """TODO: similar ao buy, com âncoras específicas de venda."""
    return False
