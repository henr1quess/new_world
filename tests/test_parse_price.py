import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.ocr import engine, extract


def setup_module(module):
    engine.PRICE_RE = re.compile(r"(\d+(?:[\.,]\d{3})*(?:[\.,]\d{1,2})?)")


def test_parse_price_simple_integer():
    assert extract.parse_price("1234") == 1234.0


def test_parse_price_decimal_comma():
    assert extract.parse_price("1.234,56") == 1234.56


def test_parse_price_decimal_dot():
    assert extract.parse_price("1,234.56") == 1234.56


def test_parse_price_ignores_noise():
    assert extract.parse_price("Preço: 999,99 coins") == 999.99


def test_parse_price_returns_none_when_no_match():
    assert extract.parse_price("N/A") is None
