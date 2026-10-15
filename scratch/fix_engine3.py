import re
from pathlib import Path

content = Path('src/extraction/engine.py').read_text('utf-8')

# Let's cleanly inject current_section_marks
import ast
# Better to do simple string replace:
old_sig = '''def _to_extracted(marker: _Marker, section_label: str | None) -> ExtractedQuestion:'''
new_sig = '''def _to_extracted(marker: _Marker, section_label: str | None, section_marks: float | None = None) -> ExtractedQuestion:'''
content = content.replace(old_sig, new_sig)

old_ret = '''        marks=extract_marks_extended(marker.raw_text),'''
new_ret = '''        marks=extract_marks_extended(marker.raw_text) or section_marks,'''
content = content.replace(old_ret, new_ret)

content = content.replace('''        current_section: str | None = None
        pending_top: _Marker | None = None
        pending_top_had_subs = False''', '''        current_section: str | None = None
        current_section_marks: float | None = None
        pending_top: _Marker | None = None
        pending_top_had_subs = False''')

content = content.replace('''            if pending_top is not None and not pending_top_had_subs:
                results.append(_to_extracted(pending_top, current_section))''', '''            if pending_top is not None and not pending_top_had_subs:
                results.append(_to_extracted(pending_top, current_section, current_section_marks))''')

content = content.replace('''            if marker.level == "section":
                flush_pending_top()
                current_section = marker.raw_text.splitlines()[0].strip() if marker.raw_text else marker.number
                continue''', '''            if marker.level == "section":
                flush_pending_top()
                current_section = marker.raw_text.splitlines()[0].strip() if marker.raw_text else marker.number
                current_section_marks = extract_marks_extended(marker.raw_text)
                continue''')

content = content.replace('''                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text),''', '''                    marks=extract_marks_extended(marker.raw_text) or extract_marks_extended(stem_text) or current_section_marks,''')

Path('src/extraction/engine.py').write_text(content, 'utf-8')

# Fix tests
test_content = Path('tests/test_phase1a.py').read_text('utf-8')
test_content = test_content.replace("'Define edge chromatic number of a graph.'", "'6\\nDefine edge chromatic number of a graph.'")
Path('tests/test_phase1a.py').write_text(test_content, 'utf-8')
