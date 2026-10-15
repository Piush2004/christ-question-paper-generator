"""Question extraction engine (master-prompt §10/§11).

Deterministic two-pass approach:
  1. Classify every line as a section header / top-level question marker / sub-question marker / body
     text, producing an ordered list of `_Marker`s.
  2. Walk the markers to assign each one's raw text span (start of this marker's line to the start of
     the next marker of any level) and reconstruct the section > top-level > sub-question hierarchy.

A sub-question's `raw_text` is its parent top-level stem plus its own body — nothing is thrown away,
per §9 ("never destroy the original source"). See `docs/RESEARCH_DECISION_LOG.md` for why this is a
rule engine rather than a learned segmenter.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.extraction.patterns import (
    SECTION_HEADER,
    SUB_QUESTION_ALPHA,
    SUB_QUESTION_ROMAN,
    TOP_LEVEL_QUESTION,
    extract_marks_extended, extract_co_rbt, OR_MARKER,
    is_valid_roman,
)
from src.ingestion.loaders import DocumentText


@dataclass
class ExtractedQuestion:
    question_number_raw: str
    raw_text: str
    page_number: int
    section_label: str | None = None
    marks: float | None = None
    is_subquestion: bool = False
    parent_number_raw: str | None = None
    extraction_confidence: float = 1.0
    source_line_start: int = 0
    source_line_end: int = 0
    course_outcome: str | None = None
    bloom: str | None = None
    is_alternative: bool = False


@dataclass
class _Marker:
    line_index: int
    page_number: int
    level: str  # "section" | "top" | "sub"
    number: str
    y0: float = 0.0
    raw_text: str = ""  # filled in during the second pass
    end_line_index: int = 0  # filled in during the second pass; exclusive end of this marker's span


@dataclass
class _Line:
    page_number: int
    text: str
    y0: float = 0.0


class QuestionExtractor:
    """Stateless — safe to reuse across documents. `extract()` is the entry point."""

    def extract(self, doc: DocumentText) -> list[ExtractedQuestion]:
        lines = self._flatten_lines(doc)
        markers = self._classify_lines(lines)
        self._assign_spans(markers, lines)
        return self._build_hierarchy(markers)

    # --- pass 0: flatten pages into a single line stream, tagging each line with its page ---
    @staticmethod
    def _flatten_lines(doc: DocumentText) -> list[_Line]:
        lines: list[_Line] = []
        for page in doc.pages:
            if getattr(page, 'blocks', None):
                for b in page.blocks:
                    if getattr(b, 'block_type', 0) != 0: continue
                    for text_line in b.text.split("\n"):
                        lines.append(_Line(page_number=page.page_number, text=text_line, y0=b.y0))
            else:
                dummy_y = 0.0
                for raw_line in page.text.split("\n"):
                    lines.append(_Line(page_number=page.page_number, text=raw_line, y0=dummy_y))
                    dummy_y += 10.0
        return lines

    # --- pass 1: classify each line as a marker (or skip it as body text) ---
    @staticmethod
    def _classify_lines(lines: list[_Line]) -> list[_Marker]:
        markers: list[_Marker] = []
        for idx, line in enumerate(lines):
            text = line.text

            sec_m = SECTION_HEADER.match(text)
            if sec_m:
                markers.append(_Marker(line_index=idx, page_number=line.page_number,
                                        level="section", number=sec_m.group(2), y0=line.y0))
                continue

            top_m = TOP_LEVEL_QUESTION.match(text)
            if top_m:
                number = top_m.group(1) or top_m.group(2) or top_m.group(3)
                markers.append(_Marker(line_index=idx, page_number=line.page_number,
                                        level="top", number=number, y0=line.y0))
                continue

            sub_r = SUB_QUESTION_ROMAN.match(text)
            if sub_r and is_valid_roman(sub_r.group(1)):
                markers.append(_Marker(line_index=idx, page_number=line.page_number,
                                        level="sub", number=sub_r.group(1).lower(), y0=line.y0))
                continue

            sub_a = SUB_QUESTION_ALPHA.match(text)
            if sub_a:
                letter = sub_a.group(1) or sub_a.group(2)
                markers.append(_Marker(line_index=idx, page_number=line.page_number,
                                        level="sub", number=letter.lower(), y0=line.y0))
                continue

        return markers

    # --- pass 2: each marker's raw_text spans from its own line to the next marker's line ---
    @staticmethod
    def _assign_spans(markers: list[_Marker], lines: list[_Line]) -> None:
        for i, marker in enumerate(markers):
            start = marker.line_index
            end = markers[i + 1].line_index if i + 1 < len(markers) else len(lines)
            marker.raw_text = "\n".join(lines[j].text for j in range(start, end)).strip()
            marker.end_line_index = end

    # --- pass 3: reconstruct section > top > sub hierarchy into flat ExtractedQuestion records ---
    @staticmethod
    def _build_hierarchy(markers: list[_Marker]) -> list[ExtractedQuestion]:
        results: list[ExtractedQuestion] = []
        pending_top: _Marker | None = None
        pending_top_had_subs = False
        
        section_markers = [m for m in markers if m.level == "section"]
        
        def get_section_for(page_num: int, y0: float) -> tuple[str | None, float | None]:
            best_sec = None
            best_sec_marks = None
            best_tuple = (-1, -1.0)
            target = (page_num, y0)
            for sm in section_markers:
                sm_tuple = (sm.page_number, sm.y0)
                # Allow a small tolerance in y0 if they are on the same line
                if sm_tuple[0] < target[0] or (sm_tuple[0] == target[0] and sm_tuple[1] <= target[1] + 5.0):
                    if sm_tuple > best_tuple:
                        best_tuple = sm_tuple
                        best_sec = sm.raw_text.splitlines()[0].strip() if sm.raw_text else sm.number
                        best_sec_marks = extract_marks_extended(sm.raw_text)
            return best_sec, best_sec_marks

        def flush_pending_top() -> None:
            nonlocal pending_top, pending_top_had_subs
            if pending_top is not None and not pending_top_had_subs:
                sec_label, sec_marks = get_section_for(pending_top.page_number, pending_top.y0)
                results.append(_to_extracted(pending_top, sec_label, sec_marks))
            pending_top = None
            pending_top_had_subs = False

        for marker in markers:
            if marker.level == "section":
                flush_pending_top()
                continue

            if marker.level == "top":
                flush_pending_top()
                pending_top = marker
                pending_top_had_subs = False
                continue

            # level == "sub"
            pending_top_had_subs = True
            parent_number = pending_top.number if pending_top else None
            stem_text = pending_top.raw_text if pending_top else ""
            combined_text = f"{stem_text}\n{marker.raw_text}".strip() if stem_text else marker.raw_text
            full_number = f"{parent_number}({marker.number})" if parent_number else marker.number
            span_start = pending_top.line_index if pending_top else marker.line_index
            co, rbt = extract_co_rbt(combined_text)
            sec_label, sec_marks = get_section_for(marker.page_number, marker.y0)
            results.append(
                ExtractedQuestion(
                    question_number_raw=full_number,
                    raw_text=combined_text,
                    page_number=marker.page_number,
                    section_label=sec_label,
                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text) or sec_marks,
                    is_subquestion=True,
                    parent_number_raw=parent_number,
                    extraction_confidence=_confidence(combined_text, extract_marks_extended(marker.raw_text)),
                    source_line_start=span_start,
                    source_line_end=marker.end_line_index,
                    course_outcome=co,
                    bloom=rbt
                )
            )

        flush_pending_top()
        
        # Post-process results to split OR alternatives
        final_results = []
        for q in results:
            lines = q.raw_text.splitlines()
            or_indices = [i for i, line in enumerate(lines) if OR_MARKER.match(line)]
            if or_indices:
                # We have alternatives
                start = 0
                for i, or_idx in enumerate(or_indices):
                    alt_text = "\n".join(lines[start:or_idx]).strip()
                    co, rbt = extract_co_rbt(alt_text)
                    final_results.append(
                        ExtractedQuestion(
                            question_number_raw=q.question_number_raw,
                            raw_text=alt_text,
                            page_number=q.page_number,
                            section_label=q.section_label,
                            marks=extract_marks_extended(alt_text) or q.marks,
                            is_subquestion=q.is_subquestion,
                            parent_number_raw=q.parent_number_raw,
                            extraction_confidence=q.extraction_confidence,
                            source_line_start=q.source_line_start,
                            source_line_end=q.source_line_start + or_idx,
                            course_outcome=co or q.course_outcome,
                            bloom=rbt or q.bloom,
                            is_alternative=(i > 0)
                        )
                    )
                    start = or_idx + 1
                # add the last piece
                alt_text = "\n".join(lines[start:]).strip()
                co, rbt = extract_co_rbt(alt_text)
                final_results.append(
                    ExtractedQuestion(
                        question_number_raw=q.question_number_raw,
                        raw_text=alt_text,
                        page_number=q.page_number,
                        section_label=q.section_label,
                        marks=extract_marks_extended(alt_text) or q.marks,
                        is_subquestion=q.is_subquestion,
                        parent_number_raw=q.parent_number_raw,
                        extraction_confidence=q.extraction_confidence,
                        source_line_start=q.source_line_start + start,
                        source_line_end=q.source_line_end,
                        course_outcome=co or q.course_outcome,
                        bloom=rbt or q.bloom,
                        is_alternative=True
                    )
                )
            else:
                final_results.append(q)
                
        return final_results

        return results


def _to_extracted(marker: _Marker, section_label: str | None, section_marks: float | None = None) -> ExtractedQuestion:
    return ExtractedQuestion(
        question_number_raw=marker.number,
        raw_text=marker.raw_text,
        page_number=marker.page_number,
        section_label=section_label,
        marks=extract_marks_extended(marker.raw_text) or section_marks,
        is_subquestion=False,
        parent_number_raw=None,
        extraction_confidence=_confidence(marker.raw_text, extract_marks_extended(marker.raw_text)),
        source_line_start=marker.line_index,
        source_line_end=marker.end_line_index,
        course_outcome=extract_co_rbt(marker.raw_text)[0],
        bloom=extract_co_rbt(marker.raw_text)[1],
    )


def _confidence(raw_text: str, marks: float | None) -> float:
    """Heuristic extraction-confidence score, not a learned estimate — surfaces low-quality
    extractions in the dataset manifest (§12) rather than silently treating every extraction as
    equally trustworthy."""
    body_len = len(raw_text.strip())
    if body_len < 10:
        return 0.4
    if marks is not None:
        return 1.0
    return 0.8
