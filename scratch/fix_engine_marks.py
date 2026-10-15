import re
from pathlib import Path

content = Path('src/extraction/engine.py').read_text('utf-8')

bh_old = '''    @staticmethod
    def _build_hierarchy(markers: list[_Marker]) -> list[ExtractedQuestion]:
        results: list[ExtractedQuestion] = []
        current_section: str | None = None
        pending_top: _Marker | None = None'''

bh_new = '''    @staticmethod
    def _build_hierarchy(markers: list[_Marker]) -> list[ExtractedQuestion]:
        results: list[ExtractedQuestion] = []
        current_section: str | None = None
        current_section_marks: float | None = None
        pending_top: _Marker | None = None'''

content = content.replace(bh_old, bh_new)

sec_old = '''            if marker.level == "section":
                flush_pending_top()
                current_section = marker.raw_text.splitlines()[0].strip() if marker.raw_text else marker.number
                continue'''

sec_new = '''            if marker.level == "section":
                flush_pending_top()
                current_section = marker.raw_text.splitlines()[0].strip() if marker.raw_text else marker.number
                current_section_marks = extract_marks_extended(marker.raw_text)
                continue'''

content = content.replace(sec_old, sec_new)

to_add_old = '''                    section_label=current_section,
                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text),'''
to_add_new = '''                    section_label=current_section,
                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text) or current_section_marks,'''
content = content.replace(to_add_old, to_add_new)

to_ext_old = '''        page_number=marker.page_number,
        section_label=section_label,
        marks=extract_marks_extended(marker.raw_text),'''
to_ext_new = '''        page_number=marker.page_number,
        section_label=section_label,
        marks=extract_marks_extended(marker.raw_text),''' # Wait, to_extracted doesn't have access to current_section_marks because it's passed only section_label.

# Instead of relying on replace strings, let's just use Python AST or safer replaces.
