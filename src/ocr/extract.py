from datetime import datetime
import hashlib
from typing import Dict, List

try:  # PyYAML is optional for parse_price tests
    import yaml
except ModuleNotFoundError:  # pragma: no cover - will be exercised in production runs
    yaml = None

from ..capture.window import capture_rect, get_screen_resolution
from ..capture.calibrate import relative_rect
from . import engine


def _normalize_number(raw: str) -> str:
    raw = raw.strip().replace(" ", "").replace("\u00a0", "")
    separators = [i for i, ch in enumerate(raw) if ch in ",."]
    decimal_index = None
    for idx in reversed(separators):
        decimals = len(raw) - idx - 1
        if decimals in (1, 2):
            decimal_index = idx
            break

    if decimal_index is None:
        return raw.replace(",", "").replace(".", "")

    integer = raw[:decimal_index].replace(",", "").replace(".", "") or "0"
    fractional = raw[decimal_index + 1 :]
    return f"{integer}.{fractional}"


def parse_price(text: str):
    price_re = engine.PRICE_RE
    if price_re is None:
        return None
    cleaned = text.replace("\n", "").replace("\r", "").strip()
    m = price_re.search(cleaned)
    if not m:
        return None
    raw = _normalize_number(m.group(1))
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
    if yaml is None:
        raise RuntimeError("PyYAML is required to load UI profiles")
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui = yaml.safe_load(fh)
    prof = next(iter(ui["profiles"].values()))  # pega primeiro perfil como default
    cols = prof["columns"]
    screen = get_screen_resolution()

    list_zone = relative_rect(prof["anchors"]["list_zone"], screen)
    lx, ly, lw, lh = list_zone

    ocr_engine = engine.OCREngine(engine.load_ocr_config(ocr_cfg_path))

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
        name_txt, conf_name = ocr_engine.text_and_conf(name_img)

        # recorte de preço
        price_rect = (
            lx + int(cols["price"]["x"] * lw),
            y0,
            int(cols["price"]["w"] * lw),
            line_h,
        )
        price_img = capture_rect(*price_rect)
        price_txt, conf_price = ocr_engine.text_and_conf(price_img)
        price_val = parse_price(price_txt)

        if price_val is None or max(conf_name, conf_price) < engine.MIN_CONF:
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
