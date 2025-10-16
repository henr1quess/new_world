from datetime import datetime
from functools import lru_cache
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


def _load_ui_cfg(ui_cfg_path: str) -> Dict:
    path = Path(ui_cfg_path)
    mtime = path.stat().st_mtime_ns
    return _load_ui_cfg_cached(path.as_posix(), mtime)


@lru_cache(maxsize=None)
def _load_ui_cfg_cached(ui_cfg_path: str, _mtime_ns: int) -> Dict:
    with Path(ui_cfg_path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_capture_cfg(capture_cfg_path: str) -> Dict:
    path = Path(capture_cfg_path)
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime_ns
    return _load_capture_cfg_cached(path.as_posix(), mtime)


@lru_cache(maxsize=None)
def _load_capture_cfg_cached(capture_cfg_path: str, _mtime_ns: int) -> Dict:
    with Path(capture_cfg_path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def scan_once(
    source_view: str,
    ocr_cfg_path: str,
    ui_cfg_path: str,
    page_index: int = 0,
    scroll_pos: float = 0.0,
) -> List[Dict]:
    ui = _load_ui_cfg(ui_cfg_path)
    prof = next(iter(ui["profiles"].values()))

    anchors = prof.get("anchors", {})
    if (
        source_view == "BUY_LIST"
        and isinstance(anchors, dict)
        and "buy_panel_zone" in anchors
    ):
        ax = anchors["buy_panel_zone"]
        cols = prof.get("buy_panel_columns", {}) or {}
        rows_per_page = int(prof.get("buy_panel_rows", 8))
    else:
        ax = anchors["list_zone"]
        cols = prof["columns"]
        rows_per_page = int(prof.get("rows", 12))

    capture_cfg_path = Path(__file__).resolve().parents[2] / "config" / "capture.yaml"
    cap_cfg = _load_capture_cfg(str(capture_cfg_path))

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

    lx, ly, lw, lh = relative_rect(ax, base_size)

    engine = OCREngine(load_ocr_config(ocr_cfg_path))

    rows: List[Dict] = []
    line_h = int(lh / rows_per_page)
    for i in range(rows_per_page):
        y0 = ly + i * line_h
        price_rect = (
            lx + int(cols["price"]["x"] * lw),
            y0,
            int(cols["price"]["w"] * lw),
            line_h,
        )
        price_txt, conf_price = engine.text_and_conf(cap_fn(*price_rect))
        price_val = parse_price(price_txt)

        name_txt, conf_name = "", 1.0
        qty_txt, conf_qty = "", 1.0

        if "name" in cols:
            name_rect = (
                lx + int(cols["name"]["x"] * lw),
                y0,
                int(cols["name"]["w"] * lw),
                line_h,
            )
            name_txt, conf_name = engine.text_and_conf(cap_fn(*name_rect))

        if "qty" in cols:
            qty_rect = (
                lx + int(cols["qty"]["x"] * lw),
                y0,
                int(cols["qty"]["w"] * lw),
                line_h,
            )
            qty_txt, conf_qty = engine.text_and_conf(cap_fn(*qty_rect))

        conf = float(min(conf_price, conf_name, conf_qty))
        if price_val is None or conf < MIN_CONF:
            continue

        item_name = " ".join(name_txt.split()) if name_txt else ""
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
                "confidence": conf,
                "hash_row": h,
            }
        )
    return rows
