from datetime import datetime
import hashlib
from typing import Dict, List

import yaml

from ..capture.window import capture_rect, get_screen_resolution
from ..capture.calibrate import relative_rect
from .engine import MIN_CONF, PRICE_RE, OCREngine, load_ocr_config


def parse_price(text: str):
    if PRICE_RE is None:
        return None
    m = PRICE_RE.search(text.replace(" ", ""))
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except Exception:
        return None


def scan_once(
    source_view: str,
    ocr_cfg_path: str,
    ui_cfg_path: str,
    page_index: int = 0,
    scroll_pos: float = 0.0,
) -> List[Dict]:
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui = yaml.safe_load(fh)
    prof = next(iter(ui["profiles"].values()))  # pega primeiro perfil como default
    cols = prof["columns"]
    screen = get_screen_resolution()

    list_zone = relative_rect(prof["anchors"]["list_zone"], screen)
    lx, ly, lw, lh = list_zone

    engine = OCREngine(load_ocr_config(ocr_cfg_path))

    rows: List[Dict] = []
    # Exemplo simples: amostra 12 linhas verticais
    line_h = int(lh / 12)
    for i in range(12):
        y0 = ly + i * line_h
        # recorte de nome
        name_rect = (
            lx + int(cols["name"]["x"] * lw),
            y0,
            int(cols["name"]["w"] * lw),
            line_h,
        )
        name_img = capture_rect(*name_rect)
        name_txt, conf_name = engine.text_and_conf(name_img)

        # recorte de preço
        price_rect = (
            lx + int(cols["price"]["x"] * lw),
            y0,
            int(cols["price"]["w"] * lw),
            line_h,
        )
        price_img = capture_rect(*price_rect)
        price_txt, conf_price = engine.text_and_conf(price_img)
        price_val = parse_price(price_txt)

        if price_val is None or max(conf_name, conf_price) < MIN_CONF:
            continue

        item_name = " ".join(name_txt.split())
        h = hashlib.sha1(
            f"{item_name}|{price_val}|{i}|{page_index}".encode()
        ).hexdigest()
        rows.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "source_view": source_view,
                "item_name": item_name,
                "price": price_val,
                "qty_visible": None,
                "page_index": page_index,
                "scroll_pos": scroll_pos,
                "confidence": float(min(conf_name, conf_price)),
                "hash_row": h,
            }
        )
    return rows
