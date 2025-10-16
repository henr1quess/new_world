from pathlib import Path

import cv2
import yaml
from PIL import ImageGrab
import numpy as np

from ..capture.window import get_window_rect
from ..ocr.engine import OCREngine, load_ocr_config

CFG_DIR = Path(__file__).resolve().parents[2] / "config"
CFG_OCR = CFG_DIR / "ocr.yaml"
CFG_CAPTURE = CFG_DIR / "capture.yaml"


def main():
    cap = yaml.safe_load(open(CFG_CAPTURE, "r", encoding="utf-8"))
    title = (cap.get("window_title_contains") or "").strip()
    wnd = get_window_rect(title)
    if not wnd:
        raise SystemExit("Janela não encontrada. Ajuste capture.yaml.")
    x, y, w, h = wnd["x"], wnd["y"], wnd["w"], wnd["h"]
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    r = cv2.selectROI("Selecione uma área para OCR (ENTER)", frame, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    if r[2] <= 0 or r[3] <= 0:
        return
    rx, ry, rw, rh = r
    crop = frame[int(ry) : int(ry + rh), int(rx) : int(rx + rw)]
    eng = OCREngine(load_ocr_config(str(CFG_OCR)))
    txt, conf = eng.text_and_conf(crop)
    print(f"OCR: '{txt}' (conf={conf:.2f})")


if __name__ == "__main__":
    main()
