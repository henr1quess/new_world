from pathlib import Path
import time, yaml, pyautogui as pg

from ..capture.window import (
    get_window_rect, get_screen_resolution,
    capture_rect, capture_rect_in_window
)
from ..capture.calibrate import relative_rect
from ..ocr.engine import OCREngine, load_ocr_config
from ..utils.timing import sleep_ms


class ActionRunner:
    """
    Executa sequências do config/actions.yaml usando anchors do ui_profiles.yaml.
    Passos suportados:
      - click {anchor}
      - type_clear
      - type_text {text}           (suporta <item_name>)
      - key {keys: ["enter"]}
      - sleep_ms {ms}
      - wait_header_contains {text, timeout_ms}
      - wait_item_first_row {timeout_ms}
    """

    def __init__(self, cfg_ui_path: str, cfg_actions_path: str, cfg_ocr_path: str):
        self.cfg_ui_path = cfg_ui_path
        self.cfg_actions_path = cfg_actions_path
        self.cfg_ocr_path = cfg_ocr_path
        self.ui = yaml.safe_load(open(cfg_ui_path, "r", encoding="utf-8"))
        self.prof = next(iter(self.ui["profiles"].values()))
        self.actions = yaml.safe_load(open(cfg_actions_path, "r", encoding="utf-8"))["actions"]
        self.engine = OCREngine(load_ocr_config(cfg_ocr_path))

    # --- helpers base/window ---
    def _window_and_cap(self):
        cap_cfg = yaml.safe_load(open(Path(self.cfg_ui_path).resolve().parents[1] / "config" / "capture.yaml", "r", encoding="utf-8"))
        title = (cap_cfg.get("window_title_contains") or "").strip()
        wnd = get_window_rect(title) if title else None
        if wnd:
            base = (wnd["w"], wnd["h"])
            def cap(x,y,w,h): return capture_rect_in_window(wnd["x"], wnd["y"], x,y,w,h)
            origin = (wnd["x"], wnd["y"])
            return base, cap, origin
        else:
            base = get_screen_resolution()
            def cap(x,y,w,h): return capture_rect(x,y,w,h)
            return base, cap, (0,0)

    def _anchor_center_abs(self, anchor_name: str):
        anchors = self.prof["anchors"]
        if anchor_name not in anchors:
            raise RuntimeError(f"Anchor '{anchor_name}' não encontrado no ui_profiles.yaml")
        base, _, origin = self._window_and_cap()
        x,y,w,h = relative_rect(anchors[anchor_name], base)
        ax, ay = origin[0] + x + w//2, origin[1] + y + h//2
        return ax, ay

    def _ocr_text_zone(self, anchor_name: str) -> str:
        base, cap, _ = self._window_and_cap()
        x,y,w,h = relative_rect(self.prof["anchors"][anchor_name], base)
        img = cap(x,y,w,h)
        txt, _ = self.engine.text_and_conf(img)
        return " ".join((txt or "").split()).lower()

    def _ocr_first_row_name(self) -> str:
        base, cap, _ = self._window_and_cap()
        lx, ly, lw, lh = relative_rect(self.prof["anchors"]["list_zone"], base)
        cols = self.prof["columns"]
        line_h = int(lh / 12)
        y0 = ly
        name_rect = (lx + int(cols["name"]["x"] * lw), y0, int(cols["name"]["w"] * lw), line_h)
        img = cap(*name_rect)
        txt, _ = self.engine.text_and_conf(img)
        return " ".join((txt or "").split()).lower()

    # --- primitives ---
    def click(self, anchor_name: str):
        ax, ay = self._anchor_center_abs(anchor_name)
        pg.moveTo(ax, ay, duration=0.05)
        pg.click()
        sleep_ms(150)

    def type_clear(self):
        pg.hotkey("ctrl","a"); sleep_ms(40)
        pg.press("backspace"); sleep_ms(40)

    def type_text(self, text: str):
        pg.write(text, interval=0.02)
        sleep_ms(200)

    def key(self, keys):
        if isinstance(keys, str):
            pg.press(keys)
        else:
            for k in keys:
                pg.press(k)
        sleep_ms(120)

    def wait_header_contains(self, text: str, timeout_ms: int = 2000) -> bool:
        t0 = time.time()
        needle = (text or "").lower()
        while (time.time() - t0) * 1000 < timeout_ms:
            got = self._ocr_text_zone("header_row")
            if needle in got:
                return True
            sleep_ms(150)
        return False

    def wait_item_first_row(self, expected: str, timeout_ms: int = 3000) -> bool:
        t0 = time.time()
        needle = (expected or "").lower()
        while (time.time() - t0) * 1000 < timeout_ms:
            got = self._ocr_first_row_name()
            if needle and needle in got:
                return True
            sleep_ms(150)
        return False

    # --- executor ---
    def run(self, action_name: str, ctx: dict | None = None) -> bool:
        steps = self.actions.get(action_name, {}).get("steps", [])
        ctx = ctx or {}
        ok = True
        for st in steps:
            typ = st["type"]
            if typ == "click":
                self.click(st["anchor"])
            elif typ == "type_clear":
                self.type_clear()
            elif typ == "type_text":
                txt = st.get("text","")
                txt = txt.replace("<item_name>", ctx.get("item_name",""))
                self.type_text(txt)
            elif typ == "key":
                self.key(st.get("keys", []))
            elif typ == "sleep_ms":
                sleep_ms(st.get("ms",150))
            elif typ == "wait_header_contains":
                ok = self.wait_header_contains(st.get("text",""), st.get("timeout_ms",2000))
                if not ok: return False
            elif typ == "wait_item_first_row":
                ok = self.wait_item_first_row(ctx.get("item_name",""), st.get("timeout_ms",3000))
                if not ok: return False
            else:
                raise RuntimeError(f"Passo não suportado: {typ}")
        return ok
