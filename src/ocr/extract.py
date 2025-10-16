from datetime import datetime
import hashlib
from typing import List, Dict
from pathlib import Path
import yaml

from ..capture.window import get_screen_resolution, capture_rect, get_window_rect, capture_rect_in_window
from .engine import OCREngine, load_ocr_config
import re

def _compile_price_re(pattern: str):
    return re.compile(pattern)

def _parse_price(text: str, price_re):
    m = price_re.search(text.replace(" ", ""))
    if not m: return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try: return float(raw)
    except: return None

def scan_once(source_view: str, ocr_cfg_path: str, ui_cfg_path: str, page_index=0, scroll_pos=0.0) -> List[Dict]:
    ocr_cfg = load_ocr_config(ocr_cfg_path)
    price_re = _compile_price_re(ocr_cfg["postprocess"]["price_regex"])
    min_conf = float(ocr_cfg["postprocess"]["min_confidence"])

    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui = yaml.safe_load(fh)
    prof = next(iter(ui["profiles"].values()))
    cols = prof["columns"]

    # Tenta capturar relativo à janela do jogo
    cap_path = Path(__file__).resolve().parents[2] / "config" / "capture.yaml"
    with open(cap_path, "r", encoding="utf-8") as fh:
        cap_cfg = yaml.safe_load(fh)
    title_sub = (cap_cfg.get("window_title_contains") or "").strip()

    wnd = get_window_rect(title_sub) if title_sub else None
    if wnd:
        wx, wy, ww, wh = wnd["x"], wnd["y"], wnd["w"], wnd["h"]
        base_size = (ww, wh)
        def cap(x, y, w, h):  # relativo à janela
            return capture_rect_in_window(wx, wy, x, y, w, h)
    else:
        # fallback: tela inteira
        sw, sh = get_screen_resolution()
        base_size = (sw, sh)
        def cap(x, y, w, h):
            return capture_rect(x, y, w, h)

    # Áreas relativas (ao base_size)
    def rel_to_abs(rel):
        bw, bh = base_size
        return (int(rel["x"]*bw), int(rel["y"]*bh), int(rel["w"]*bw), int(rel["h"]*bh))

    list_zone = rel_to_abs(prof["anchors"]["list_zone"])
    lx, ly, lw, lh = list_zone

    engine = OCREngine(ocr_cfg)

    rows = []
    # Amostra 12 linhas por "página" simples (MVP)
    line_h = int(lh / 12)
    for i in range(12):
        y0 = ly + i * line_h

        name_rect = (lx + int(cols["name"]["x"]*lw), y0, int(cols["name"]["w"]*lw), line_h)
        name_img = cap(*name_rect)
        name_txt, conf_name = engine.text_and_conf(name_img)

        price_rect = (lx + int(cols["price"]["x"]*lw), y0, int(cols["price"]["w"]*lw), line_h)
        price_img = cap(*price_rect)
        price_txt, conf_price = engine.text_and_conf(price_img)

        price_val = _parse_price(price_txt, price_re)

        if price_val is None or max(conf_name, conf_price) < min_conf:
            continue

        item_name = " ".join(name_txt.split())
        h = hashlib.sha1(f"{item_name}|{price_val}|{i}|{page_index}".encode()).hexdigest()
        rows.append({
            "timestamp": datetime.utcnow().isoformat(),
            "source_view": source_view,
            "item_name": item_name,
            "price": price_val,
            "qty_visible": None,
            "page_index": page_index,
            "scroll_pos": scroll_pos,
            "confidence": float(min(conf_name, conf_price)),
            "hash_row": h
        })
    return rows
