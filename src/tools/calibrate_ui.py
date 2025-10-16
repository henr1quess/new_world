from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import ImageGrab

from src.capture.window import get_window_rect
from src.capture.calibrate import relative_rect

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
]
OPTIONAL_ANCHORS = [
    "my_orders_tab",
    "place_buy_button",
    "buy_panel_zone",
    "buy_panel_close",
]
REQUIRED_COLUMNS = ["name", "price", "qty"]
BUY_PANEL_COLUMNS = ["price", "qty"]  # se calibrar buy_panel_zone


# ---------- helpers de captura/UX ----------

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


def _select_roi(img, title, help_text="Arraste o retângulo e tecle ENTER (ESC para cancelar)."):
    tmp = img.copy()
    cv2.putText(tmp, help_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 200, 40), 2, cv2.LINE_AA)
    cv2.imshow(title, tmp)
    cv2.waitKey(50)
    r = cv2.selectROI(title, img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(title)
    x, y, w, h = r
    return (int(x), int(y), int(w), int(h)) if w > 0 and h > 0 else None


def _preview_confirm(img, roi, title, allow_skip: bool) -> str:
    """
    Mostra um preview com instruções e retorna:
      'ok' | 'resnap' | 'skip'
    """
    x, y, w, h = roi
    tmp = img.copy()
    cv2.rectangle(tmp, (x, y), (x + w, y + h), (0, 255, 255), 2)
    msg = "ENTER: confirmar  •  R: refazer print  " + ("•  S: pular" if allow_skip else "")
    cv2.putText(tmp, msg, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 220, 30), 2, cv2.LINE_AA)
    win_name = f"Preview — {title}"
    cv2.imshow(win_name, tmp)
    while True:
        k = cv2.waitKey(0) & 0xFF
        if k in (13, 10, 32):  # Enter/Return/Space
            cv2.destroyWindow(win_name)
            return "ok"
        if k in (ord("r"), ord("R")):
            cv2.destroyWindow(win_name)
            return "resnap"
        if allow_skip and k in (ord("s"), ord("S")):
            cv2.destroyWindow(win_name)
            return "skip"


def _norm(rect, base):
    x, y, w, h = rect
    bw, bh = base
    return {"x": round(x / bw, 5), "y": round(y / bh, 5), "w": round(w / bw, 5), "h": round(h / bh, 5)}


def _snap_prompt(what: str):
    input(f"\n➡️ Deixe **{what}** VISÍVEL no jogo e pressione ENTER aqui para fotografar... ")


def _choose_anchor_interactive(anchor_name: str, base_hint: tuple[int, int] | None, allow_skip: bool):
    """
    Laço: tira print → seleciona ROI → preview (ENTER/R/S)
    Retorna dict normalizado OU None se pulado.
    """
    while True:
        # novo snapshot
        (_, _, ww, wh), img = _grab_window_img()
        base = (ww, wh)
        roi = _select_roi(img, f"Anchor: {anchor_name}")
        if not roi:
            # sem ROI: força resnap ou skip via prompt
            resp = input("Nenhuma seleção feita. [ENTER] refazer • (s) pular: ").strip().lower()
            if allow_skip and resp == "s":
                return None, base
            else:
                continue
        decision = _preview_confirm(img, roi, f"Anchor: {anchor_name}", allow_skip)
        if decision == "ok":
            return _norm(roi, base), base
        if decision == "skip" and allow_skip:
            return None, base
        # decision == 'resnap' → volta pro while e tira outro print


def _choose_column_interactive(sub_img, col_name: str, tip: str = "Selecione apenas a LARGURA da coluna (altura tanto faz)."):
    while True:
        roi = _select_roi(
            sub_img,
            f"Column: {col_name}",
            tip + "  ENTER confirma • R refaz print (da tela inteira) • S pula",
        )
        if not roi:
            # sem ROI na sub-imagem: oferecer refazer print total
            resp = input("Coluna não selecionada. [ENTER] refazer print da tela • (s) pular coluna: ").strip().lower()
            if resp == "s":
                return None
            # pedido de refazer print será tratado no nível acima (que refaz sub_img)
            return "RESNAP"
        # Preview rápido (sem atalhos de janela; confirmação no console)
        x, y, w, h = roi
        tmp = sub_img.copy()
        cv2.rectangle(tmp, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.imshow(f"Preview — Column: {col_name}", tmp)
        k = cv2.waitKey(0) & 0xFF
        cv2.destroyAllWindows()
        if k in (ord("r"), ord("R")):
            return "RESNAP"
        if k in (ord("s"), ord("S")):
            return None
        return roi  # ENTER/qualquer outra tecla → aceitar


# ---------- fluxo principal ----------

def main(profile: str = ""):
    # Carrega UI existente (para permitir skip de âncoras já configuradas)
    ui = {}
    if CFG_UI.exists():
        with open(CFG_UI, "r", encoding="utf-8") as fh:
            ui = yaml.safe_load(fh) or {}
    ui.setdefault("profiles", {})

    # Descobre resolução inicial
    (wx, wy, ww, wh), _ = _grab_window_img()
    if not profile:
        profile = f"{ww}x{wh}@100%"

    existing_profile = ui["profiles"].get(profile, {}) if ui["profiles"] else {}
    existing_anchors = (existing_profile.get("anchors") or {}) if isinstance(existing_profile, dict) else {}

    anchors: dict[str, dict] = dict(existing_anchors)  # começa herdando o que já existe

    print("== Seleção de ÂNCORAS (um snapshot por âncora) ==")
    for name in REQUIRED_ANCHORS:
        # se já existe, oferecer pular
        if name in anchors:
            resp = input(f"Âncora '{name}' já existe. Pular? [S/n] ").strip().lower()
            if resp in ("", "s"):
                continue
        _snap_prompt(f"anchor '{name}'")
        allow_skip = name in existing_anchors  # só deixa pular se já existia
        sel, base = _choose_anchor_interactive(name, (ww, wh), allow_skip=allow_skip)
        if sel is None:
            if not allow_skip:
                raise SystemExit(f"Âncora obrigatória '{name}' não definida e não havia valor anterior. Abortando.")
            # skipar mantendo a anterior
        else:
            anchors[name] = sel

    # Opcionais
    print("\n== Âncoras opcionais ==")
    for name in OPTIONAL_ANCHORS:
        if name in anchors:
            resp0 = input(f"'{name}' já existe. Pular? [S/n] ").strip().lower()
            if resp0 in ("", "s"):
                continue
        resp = input(f"Deseja calibrar '{name}' agora? [s/N] ").strip().lower()
        if resp != "s":
            continue
        _snap_prompt(f"anchor opcional '{name}'")
        sel, base = _choose_anchor_interactive(name, (ww, wh), allow_skip=True)
        if sel is not None:
            anchors[name] = sel

    # Colunas na lista principal
    print("\n== Colunas da LISTA principal (dentro de list_zone) ==")
    while True:
        _snap_prompt("a LISTA do book visível (list_zone)")
        (_, _, ww, wh), img = _grab_window_img()
        base = (ww, wh)
        lx, ly, lw, lh = relative_rect(anchors["list_zone"], base)
        sub = img[int(ly) : int(ly + lh), int(lx) : int(lx + lw)].copy()

        cols = {}
        need_resnap = False
        for cname in REQUIRED_COLUMNS:
            r = _choose_column_interactive(
                sub,
                cname,
                "Selecione apenas a LARGURA da coluna (altura tanto faz).",
            )
            if r == "RESNAP":
                need_resnap = True
                break
            if r is None:
                raise SystemExit(f"Coluna obrigatória '{cname}' não definida.")
            rx, ry, rw, rh = r
            cols[cname] = {"x": round(rx / lw, 5), "w": round(rw / lw, 5)}
        if need_resnap:
            # volta ao início do laço para tirar outro print da tela inteira
            continue
        break

    # Colunas no painel de buy (se calibrado)
    buy_panel_cols = None
    if "buy_panel_zone" in anchors:
        print("\n== Colunas do painel de BUY (opcional) ==")
        while True:
            _snap_prompt("o painel de BUY aberto")
            (_, _, ww, wh), img2 = _grab_window_img()
            base2 = (ww, wh)
            bx, by, bw, bh = relative_rect(anchors["buy_panel_zone"], base2)
            sub2 = img2[int(by) : int(by + bh), int(bx) : int(bx + bw)].copy()

            buy_panel_cols = {}
            need_resnap2 = False
            for cname in BUY_PANEL_COLUMNS:
                r = _choose_column_interactive(sub2, cname)
                if r == "RESNAP":
                    need_resnap2 = True
                    break
                if r is None:
                    # coluna opcional — simplesmente pula
                    continue
                rx, ry, rw, rh = r
                buy_panel_cols[cname] = {"x": round(rx / bw, 5), "w": round(rw / bw, 5)}
            if need_resnap2:
                continue
            break

    # Salva perfil
    prof_obj = {
        "anchors": anchors,
        "columns": cols,
        "scroll": {"step_pixels": 240, "pause_ms": 150},
        "rows": 12,
    }
    if buy_panel_cols:
        prof_obj["buy_panel_columns"] = buy_panel_cols
        prof_obj["buy_panel_rows"] = 8
        prof_obj["buy_panel_scroll"] = {"step_pixels": 180, "pause_ms": 150}

    ui["profiles"][profile] = prof_obj

    with open(CFG_UI, "w", encoding="utf-8") as fh:
        yaml.safe_dump(ui, fh, allow_unicode=True, sort_keys=False)
    print(f"\n✅ OK. Perfil '{profile}' salvo em {CFG_UI}")


if __name__ == "__main__":
    main()
