import re

import numpy as np
from PIL import Image
import yaml

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - optional dependency
    PaddleOCR = None

import pytesseract

PRICE_RE = None
MIN_CONF = 0.65


def load_ocr_config(path_ocr_yaml: str):
    """Load OCR configuration file and set global parameters."""
    global PRICE_RE, MIN_CONF
    with open(path_ocr_yaml, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    PRICE_RE = re.compile(cfg["postprocess"]["price_regex"])
    MIN_CONF = float(cfg["postprocess"]["min_confidence"])
    tess_cfg = cfg.get("tesseract", {})
    if tess_cfg.get("path"):
        pytesseract.pytesseract.tesseract_cmd = tess_cfg["path"]
    return cfg


class OCREngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.paddle = None
        if "paddle" in cfg.get("engine_order", []) and PaddleOCR is not None:
            self.paddle = PaddleOCR(
                use_angle_cls=False,
                use_gpu=False,
                det=True,
                rec=True,
                lang="en",
            )

    def text_and_conf(self, img: Image.Image) -> tuple[str, float]:
        # 1) Paddle
        if self.paddle:
            res = self.paddle.ocr(np.array(img), cls=False)
            if res and res[0]:
                # pega a linha com melhor confiança média
                best = max(res[0], key=lambda r: float(r[1][1]))
                return best[1][0], float(best[1][1])
        # 2) Tesseract fallback
        txt = pytesseract.image_to_string(
            img, config=f'--psm {self.cfg["tesseract"]["psm"]}'
        )
        return txt.strip(), 0.60
