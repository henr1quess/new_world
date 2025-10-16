import re
from typing import Optional, Tuple

import numpy as np
import pytesseract
import yaml
from PIL import Image

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - optional dependency
    PaddleOCR = None

PRICE_RE = None
MIN_CONF = 0.65


def load_ocr_config(path_ocr_yaml: str):
    global PRICE_RE, MIN_CONF
    with open(path_ocr_yaml, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    PRICE_RE = re.compile(cfg["postprocess"]["price_regex"])
    MIN_CONF = float(cfg["postprocess"]["min_confidence"])
    tesseract_cfg = cfg.get("tesseract", {})
    tess_path = tesseract_cfg.get("path")
    if tess_path:
        pytesseract.pytesseract.tesseract_cmd = tess_path
    return cfg


class OCREngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.paddle: Optional[object] = None
        if "paddle" in cfg.get("engine_order", []) and PaddleOCR is not None:
            self.paddle = PaddleOCR(
                use_angle_cls=False,
                use_gpu=False,
                det=True,
                rec=True,
                lang="en",
            )

    def text_and_conf(self, img: Image.Image) -> Tuple[str, float]:
        # 1) PaddleOCR
        if self.paddle is not None:
            arr = np.array(img)
            res = self.paddle.ocr(arr, cls=False)
            if res and res[0]:
                best = max(res[0], key=lambda r: float(r[1][1]))
                return best[1][0], float(best[1][1])
        # 2) Tesseract fallback
        txt = pytesseract.image_to_string(
            img, config=f'--psm {self.cfg["tesseract"]["psm"]}'
        )
        return txt.strip(), 0.60
