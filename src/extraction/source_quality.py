"""Source-question quality status. The original question text is NEVER altered or deleted; each question
gets a status + reasons that decide whether it may be used as a training / exemplar / evaluation-reference
item. Two independent evidence sources, always recorded separately:

  deterministic  — extraction-level defects detectable by rules (lost math, dangling data, truncation)
  llm_screen     — a moderator-style LLM pass; it can only raise NEEDS_HUMAN_REVIEW, never declare a
                   question ILL_POSED/AMBIGUOUS (those need a human; no human review exists yet)

Statuses: VALID | EXTRACTION_ERROR | INCOMPLETE | NEEDS_HUMAN_REVIEW  (ILL_POSED / AMBIGUOUS are reserved
for human adjudication and are never assigned automatically).
"""

from __future__ import annotations

import re

VALID, EXTRACTION_ERROR, INCOMPLETE, NEEDS_REVIEW = "VALID", "EXTRACTION_ERROR", "INCOMPLETE", "NEEDS_HUMAN_REVIEW"

_DANGLING = re.compile(r"\b(given (below|above)|following [a-z\- ]{0,30}?(graph|figure|diagram|table|matrix|network|tree|circuit|"
                       r"data|values|information|dataset)|shown (below|above)|figure \d|fig\.|refer (to )?the (figure|diagram|table))\b",
                       re.IGNORECASE)
_MATH_GLYPHS = re.compile("[\U0001D400-\U0001D7FF]")      # mathematical alphanumerics (readable, but a sign of math text)
_PRIVATE_USE = re.compile("[-�]")         # glyphs the PDF could not map to Unicode
_LIST_MARKER = re.compile(r"(?:(?<=\s)|^)(?:[a-z]|[ivx]{1,4}|\d{1,2})\)(?=\s)", re.IGNORECASE)
_ISOLATED = re.compile(r"(?:\s|^)[A-Za-z0-9](?=\s|$)")


def deterministic_status(text: str, marks: float | None = None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    t = text.strip()
    words = t.split()
    if _PRIVATE_USE.search(t):
        reasons.append("unmapped_glyphs")
    if len(words) < 3:
        reasons.append("text_too_short_for_a_question (formula/figure content lost in extraction)")
    iso = len(_ISOLATED.findall(" " + t))
    if len(words) >= 6 and iso / len(words) > 0.35 and not _MATH_GLYPHS.search(t):
        reasons.append("fragmented_tokens (formula text broken apart)")
    body = _LIST_MARKER.sub(" ", t)          # "a)", "ii)", "3)" list markers are not brackets
    if body.count("(") != body.count(")") or body.count("{") != body.count("}"):
        reasons.append("unbalanced_brackets (possible truncation)")
    status = EXTRACTION_ERROR if reasons else VALID
    inc = []
    if t.endswith(":"):
        inc.append("ends_with_colon_without_the_data")
    if _DANGLING.search(t):
        inc.append("refers_to_figure_table_or_data_not_in_text")
    if inc:
        reasons += inc
        status = INCOMPLETE if status == VALID else status
    return status, reasons


def combine(det_status: str, det_reasons: list[str], llm: dict | None) -> tuple[str, list[str]]:
    """Overall status. The LLM screen can only add NEEDS_HUMAN_REVIEW on top of a deterministic VALID."""
    reasons = list(det_reasons)
    status = det_status
    if llm and status == VALID:
        flags = [k for k in ("needs_missing_data", "out_of_scope", "ambiguous") if llm.get(k)]
        if llm.get("answerable") is False:
            flags.append("not_answerable_as_written")
        if flags:
            status = NEEDS_REVIEW
            reasons += [f"llm_screen:{f}" for f in flags]
    return status, reasons


def eligible_for_exemplars(status: str) -> bool:
    """Used as exemplar/cluster material for generation and as supervised data. Copy-detection always uses
    ALL questions regardless of status."""
    return status in (VALID, NEEDS_REVIEW)   # deterministic defects are excluded; LLM-flagged are kept but disclosed
