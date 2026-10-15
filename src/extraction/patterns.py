"""Regex grammar for question/section/marks detection (master-prompt §10)."""
from __future__ import annotations
import re

ROMAN_NUMERAL = r"(?:x{0,3}(?:ix|iv|v?i{0,3}))"

SECTION_HEADER = re.compile(
    r"^\s*(section|part)\s*[-:]?\s*([A-Z]|[IVXivx]+|\d+)\b",
    re.IGNORECASE,
)

TOP_LEVEL_QUESTION = re.compile(
    r"^\s*(?:(?:Q(?:uestion)?\.?\s*)(\d{1,3})\b\.?|(\d{1,3})[.)](?:\s+|$)|(\d{1,3})\s*$)",
    re.IGNORECASE,
)

SUB_QUESTION_ALPHA = re.compile(r"^\s*\(?([a-h])\)[.\s]|^\s*\(?([a-h])\)\s*$", re.IGNORECASE)
SUB_QUESTION_ROMAN = re.compile(
    rf"^\s*\(?({ROMAN_NUMERAL})\)[.\s]",
    re.IGNORECASE,
)

MARKS_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[\[\(]\s*(\d+(?:\.\d+)?)\s*(?:marks?|m)?\s*[\]\)]"
    r"|(?<![A-Za-z0-9_])(\d+(?:\.\d+)?)\s*marks\b"
    r"|(?<![A-Za-z0-9_])(\d+(?:\.\d+)?)\s*M\b",
    re.IGNORECASE,
)

TRAILING_MARKS_CO_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*\(\s*(CO\d|L\d)", re.IGNORECASE
)
SECTION_MARKS_PATTERN = re.compile(
    r"\b(\d+)\s*\D+\s*(\d+)\s*=\s*(\d+)\b", re.IGNORECASE
)
OR_MARKER = re.compile(r"^\s*OR\s*$", re.IGNORECASE)

def is_valid_roman(token: str) -> bool:
    return bool(re.fullmatch(r"(x{0,3}(ix|iv|v?i{1,3}|v))", token, re.IGNORECASE)) and token != ""

def extract_marks(line: str) -> float | None:
    return extract_marks_extended(line)

def extract_marks_extended(text: str) -> float | None:
    match3 = SECTION_MARKS_PATTERN.search(text)
    if match3:
        try:
            return float(match3.group(2))
        except:
            pass
    match = MARKS_PATTERN.search(text)
    if match:
        for group in match.groups():
            if group is not None:
                return float(group)
    for line in text.splitlines():
        match2 = TRAILING_MARKS_CO_PATTERN.search(line)
        if match2:
            return float(match2.group(1))
    return None

def extract_co_rbt(text: str):
    co = None
    rbt = None
    co_match = re.search(r"\b(CO[1-6])\b", text, re.IGNORECASE)
    if co_match:
        co = co_match.group(1).upper()
    rbt_match = re.search(r"\b(L[1-6])\b", text, re.IGNORECASE)
    if rbt_match:
        rbt = rbt_match.group(1).upper()
    return co, rbt
