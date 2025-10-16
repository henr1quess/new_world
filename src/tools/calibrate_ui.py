from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import ImageGrab

from ..capture.window import get_window_rect
from ..capture.calibrate import relative_rect

CFG_DIR = Path(__file__).resolve().parents[2] / "config"
CFG_UI = CFG_DIR / "ui_profiles.yaml"
CFG_CAPTURE = CFG_DIR / "capture.yaml"

REQUIRED_ANCHORS = [
    "search_box",
    "results_zone",
    "buy_tab",
    "sell_tab",
    "header_row",
    "list_zone",
    "footer_zone",
    "buy_panel_zone",
    "my_orders_zone",
]
REQUIRED_COLUMNS = ["name", "price", "qty"]
BUY_PANEL_COLUMNS = ["price", "qty"]
MY_ORDERS_COLUMNS = ["price", "qty_remaining"]
MY_ORDERS_OPTIONAL_COLUMNS = ["item_name", "side"]

def _grab_window_img():
    with open(CFG_CAPTURE, "r", encoding="utf-8") as fh:
        cap = yaml.safe_load(fh)
    title = (cap.get("window_title_contains") or "").strip()
    wnd = get_window_rect(title) if title else None
    if not wnd:
        raise SystemExit("Janela do jogo não encontrada. Ajuste config/capture.yaml: window_title_contains.")
    x, y, w, h = wnd["x"], wnd["y"], wnd["w"], wnd["h"]
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    arr = np.array(img)
    return (x, y, w, h), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def _select_roi(img, title, help_text="Selecione e tecle ENTER (ESC para pular)."):
    tmp = img.copy()
    cv2.putText(tmp, help_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40,200,40), 2, cv2.LINE_AA)
    cv2.imshow(title, tmp)
    cv2.waitKey(50)
    r = cv2.selectROI(title, img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(title)
    x,y,w,h = r
    return (int(x), int(y), int(w), int(h)) if w>0 and h>0 else None

def _norm(rect, base):
    x,y,w,h = rect
    bw,bh = base
    return {"x": round(x/bw,5), "y": round(y/bh,5), "w": round(w/bw,5), "h": round(h/bh,5)}


def _select_columns_in_zone(
    img,
    base,
    anchors,
    zone_key: str,
    required_cols,
    optional_cols=None,
    title_prefix: str = "",
):
    print(f"== Seleção de COLUNAS (dentro de {zone_key}) ==")
    lx, ly, lw, lh = relative_rect(anchors[zone_key], base)
    sub = img[int(ly):int(ly+lh), int(lx):int(lx+lw)].copy()

    cols = {}
    for cname in required_cols:
        roi = _select_roi(sub, f"{title_prefix}Column: {cname}", "Selecione a largura/área da coluna (ENTER).")
        if not roi:
            raise SystemExit(f"Coluna obrigatória '{cname}' não definida.")
        rx,ry,rw,rh = roi
        cols[cname] = {
            "x": round((rx)/lw,5),
            "w": round(rw/lw,5)
        }

    for cname in optional_cols or []:
        roi = _select_roi(
            sub,
            f"{title_prefix}Column: {cname}",
            "Selecione a coluna (ENTER) ou ESC para pular.",
        )
        if not roi:
            continue
        rx,ry,rw,rh = roi
        cols[cname] = {
            "x": round((rx)/lw,5),
            "w": round(rw/lw,5)
        }
    return cols


def main(profile: str = ""):
    (wx,wy,ww,wh), img = _grab_window_img()
    base = (ww, wh)

    anchors = {}
    print("== Seleção de ÂNCORAS ==")
    for name in REQUIRED_ANCHORS:
        roi = _select_roi(img, f"Anchor: {name}")
        if not roi:
            raise SystemExit(f"Âncora obrigatória '{name}' não definida.")
        anchors[name] = _norm(roi, base)

    cols = _select_columns_in_zone(img, base, anchors, "list_zone", REQUIRED_COLUMNS)
    buy_panel_cols = _select_columns_in_zone(
        img,
        base,
        anchors,
        "buy_panel_zone",
        BUY_PANEL_COLUMNS,
        title_prefix="Buy Panel "
    )
    my_orders_cols = _select_columns_in_zone(
        img,
        base,
        anchors,
        "my_orders_zone",
        MY_ORDERS_COLUMNS,
        optional_cols=MY_ORDERS_OPTIONAL_COLUMNS,
        title_prefix="My Orders "
    )

    # carregar UI existente (se houver) e inserir/atualizar perfil
    ui = {}
    if CFG_UI.exists():
        with open(CFG_UI, "r", encoding="utf-8") as fh:
            ui = yaml.safe_load(fh) or {}
    ui.setdefault("profiles", {})

    if not profile:
        profile = f"{ww}x{wh}@100%"

    ui["profiles"][profile] = {
        "anchors": anchors,
        "columns": cols,
        "buy_panel_columns": buy_panel_cols,
        "my_orders_columns": my_orders_cols,
        "scroll": {"step_pixels": 240, "pause_ms": 150}
    }

    with open(CFG_UI, "w", encoding="utf-8") as fh:
        yaml.safe_dump(ui, fh, allow_unicode=True, sort_keys=False)
    print(f"OK. Perfil '{profile}' salvo em {CFG_UI}")

if __name__ == "__main__":
    main()
