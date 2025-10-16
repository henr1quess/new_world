"""OCR engine abstraction built on top of pytesseract."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import yaml
import pytesseract
from pytesseract import Output
from PIL import Image


def load_ocr_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class OCREngine:
    """Simple OCR helper that wraps pytesseract for text and confidence extraction."""

    def __init__(self, config: Dict):
        self.config = config
        self._tess_config = self._build_tesseract_config()

    def _build_tesseract_config(self) -> str:
        tess_cfg = self.config.get("tesseract", {})

        tesseract_path = tess_cfg.get("path")
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = str(Path(tesseract_path))

        options = []
        if "psm" in tess_cfg:
            options.append(f"--psm {tess_cfg['psm']}")
        if "oem" in tess_cfg:
            options.append(f"--oem {tess_cfg['oem']}")
        if "whitelist" in tess_cfg:
            whitelist = tess_cfg["whitelist"]
            options.append(f"-c tessedit_char_whitelist={whitelist}")

        return " ".join(options)

    def text_and_conf(self, image: Image.Image) -> Tuple[str, float]:
        data = pytesseract.image_to_data(image, output_type=Output.DICT, config=self._tess_config)
        words = [w for w in data.get("text", []) if w and w.strip()]
        confidences = [float(c) for c in data.get("conf", []) if c not in ("-1", "-1.0")]

        text = " ".join(words)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return text, confidence / 100.0
