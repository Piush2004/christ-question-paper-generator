import sys
from pathlib import Path
import re

file_path = Path('src/extraction/engine.py')
content = file_path.read_text('utf-8')

# 1. Update ExtractedQuestion
eq_old = '''@dataclass
class ExtractedQuestion:
    question_number_raw: str
    raw_text: str
    page_number: int
    section_label: str | None = None
    marks: float | None = None
    is_subquestion: bool = False
    parent_number_raw: str | None = None
    extraction_confidence: float = 1.0
    # 0-indexed line offsets in the document's flattened line stream (see _flatten_lines) —
    # gives finer-grained provenance than page_number alone (Phase 0.5 §4).
    source_line_start: int = 0
    source_line_end: int = 0'''

eq_new = '''@dataclass
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
    is_alternative: bool = False'''
    
content = content.replace(eq_old, eq_new)

# 2. Update imports and usages of extract_marks
content = content.replace('extract_marks,', 'extract_marks_extended, extract_co_rbt, OR_MARKER,')
content = content.replace('extract_marks(', 'extract_marks_extended(')

# 3. Handle OR blocks in _build_hierarchy
bh_old = '''            results.append(
                ExtractedQuestion(
                    question_number_raw=full_number,
                    raw_text=combined_text,
                    page_number=marker.page_number,
                    section_label=current_section,
                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text),
                    is_subquestion=True,
                    parent_number_raw=parent_number,
                    extraction_confidence=_confidence(combined_text, extract_marks_extended(marker.raw_text)),
                    source_line_start=span_start,
                    source_line_end=marker.end_line_index,
                )
            )

        flush_pending_top()'''

bh_new = '''            co, rbt = extract_co_rbt(combined_text)
            results.append(
                ExtractedQuestion(
                    question_number_raw=full_number,
                    raw_text=combined_text,
                    page_number=marker.page_number,
                    section_label=current_section,
                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text),
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
'''

content = content.replace(bh_old, bh_new)

to_ext_old = '''        marks=extract_marks_extended(marker.raw_text),
        is_subquestion=False,
        parent_number_raw=None,
        extraction_confidence=_confidence(marker.raw_text, extract_marks_extended(marker.raw_text)),
        source_line_start=marker.line_index,
        source_line_end=marker.end_line_index,
    )'''

to_ext_new = '''        marks=extract_marks_extended(marker.raw_text),
        is_subquestion=False,
        parent_number_raw=None,
        extraction_confidence=_confidence(marker.raw_text, extract_marks_extended(marker.raw_text)),
        source_line_start=marker.line_index,
        source_line_end=marker.end_line_index,
        course_outcome=extract_co_rbt(marker.raw_text)[0],
        bloom=extract_co_rbt(marker.raw_text)[1],
    )'''

content = content.replace(to_ext_old, to_ext_new)

file_path.write_text(content, 'utf-8')
print('Updated engine.py')
