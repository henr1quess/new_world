from datetime import datetime
import hashlib
from pathlib import Path
from typing import Dict, List

import yaml

from ..capture.window import (
    capture_rect,
    capture_rect_in_window,
    get_screen_resolution,
    get_window_rect,
)
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
    prof = next(iter(ui["profiles"].values()))
    cols = prof["columns"]

    capture_cfg_path = Path(__file__).resolve().parents[2] / "config" / "capture.yaml"
    if capture_cfg_path.exists():
        with open(capture_cfg_path, "r", encoding="utf-8") as fh:
            cap_cfg = yaml.safe_load(fh) or {}
    else:
        cap_cfg = {}

    title_contains = (cap_cfg.get("window_title_contains") or "").strip()
    window_info = get_window_rect(title_contains) if title_contains else None

    if window_info:
        base_size = (window_info["w"], window_info["h"])

        def cap_fn(x: int, y: int, w: int, h: int):
            return capture_rect_in_window(window_info["x"], window_info["y"], x, y, w, h)

    else:
        base_size = get_screen_resolution()

        def cap_fn(x: int, y: int, w: int, h: int):
            return capture_rect(x, y, w, h)

    lx, ly, lw, lh = relative_rect(prof["anchors"]["list_zone"], base_size)

    engine = OCREngine(load_ocr_config(ocr_cfg_path))

    rows: List[Dict] = []
    line_h = int(lh / 12)
    for i in range(12):
        y0 = ly + i * line_h

        name_rect = (
            lx + int(cols["name"]["x"] * lw),
            y0,
            int(cols["name"]["w"] * lw),
            line_h,
        )
        price_rect = (
            lx + int(cols["price"]["x"] * lw),
            y0,
            int(cols["price"]["w"] * lw),
            line_h,
        )

        name_txt, conf_name = engine.text_and_conf(cap_fn(*name_rect))
        price_txt, conf_price = engine.text_and_conf(cap_fn(*price_rect))
        price_val = parse_price(price_txt)

        if price_val is None or min(conf_name, conf_price) < MIN_CONF:
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
