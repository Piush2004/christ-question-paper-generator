from pathlib import Path
import re

content = Path('src/extraction/patterns.py').read_text('utf-8')
content = content.replace('[\*xX]', '[\*xX×]')
# Also fix the extract_marks division logic to return the mark per question (group 2)
# Wait, group(2) is the mark per question in '10 x 3 = 30' (10 questions of 3 marks)
# Let's fix extract_marks_extended
def_func_old = '''    match3 = SECTION_MARKS_PATTERN.search(text)
    if match3:
        try:
            return float(match3.group(3)) / float(match3.group(2))
        except:
            return float(match3.group(1))'''
def_func_new = '''    match3 = SECTION_MARKS_PATTERN.search(text)
    if match3:
        try:
            # 10 x 3 = 30. We want 3. So group(3)/group(1) or just group(2)!
            return float(match3.group(2))
        except:
            pass'''
content = content.replace(def_func_old, def_func_new)
Path('src/extraction/patterns.py').write_text(content, 'utf-8')
