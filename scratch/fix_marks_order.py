from pathlib import Path
import re

content = Path('src/extraction/patterns.py').read_text('utf-8')

func = '''def extract_marks_extended(text: str) -> float | None:
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
    return None'''

# Regex for section marks
content = re.sub(r'SECTION_MARKS_PATTERN = .*', r'SECTION_MARKS_PATTERN = re.compile(r"\\\\b(\\\\d+)\\\\s*\\\\D+\\\\s*(\\\\d+)\\\\s*=\\\\s*(\\\\d+)\\\\b", re.IGNORECASE)', content)

import ast
start_idx = content.find('def extract_marks_extended')
end_idx = content.find('def extract_co_rbt')
content = content[:start_idx] + func + '\n\n' + content[end_idx:]

Path('src/extraction/patterns.py').write_text(content, 'utf-8')
