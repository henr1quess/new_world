import re
from typing import Any

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional in minimal envs
    np = None  # type: ignore[assignment]

try:
    from PIL import Image as PILImage
except ModuleNotFoundError:  # pragma: no cover - optional in minimal envs
    PILImage = Any  # type: ignore[assignment]

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional in minimal envs
    yaml = None  # type: ignore[assignment]

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - optional dependency
    PaddleOCR = None

try:
    import pytesseract
except ModuleNotFoundError:  # pragma: no cover - optional in minimal envs
    pytesseract = None  # type: ignore[assignment]

PRICE_RE = None
MIN_CONF = 0.65


def load_ocr_config(path_ocr_yaml: str):
    """Load OCR configuration file and set global parameters."""
    global PRICE_RE, MIN_CONF
    if yaml is None:
        raise RuntimeError("PyYAML is required to load OCR configuration")
    with open(path_ocr_yaml, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    PRICE_RE = re.compile(cfg["postprocess"]["price_regex"])
    MIN_CONF = float(cfg["postprocess"]["min_confidence"])
    tess_cfg = cfg.get("tesseract", {})
    if tess_cfg.get("path") and pytesseract is not None:
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

    def text_and_conf(self, img: PILImage) -> tuple[str, float]:
        if pytesseract is None:
            raise RuntimeError("pytesseract is required for OCR operations")
        if np is None:
            raise RuntimeError("numpy is required for OCR operations")
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
