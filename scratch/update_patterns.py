import sys
from pathlib import Path
import re

file_path = Path('src/extraction/patterns.py')
content = file_path.read_text('utf-8')

new_patterns = '''
# --- marks: new patterns ---
TRAILING_MARKS_CO_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*\(\s*(CO\d|L\d)", re.IGNORECASE
)
SECTION_MARKS_PATTERN = re.compile(
    r"\b(\d+)\s*[\*xX]\s*(\d+)\s*=\s*(\d+)\b", re.IGNORECASE
)
OR_MARKER = re.compile(r"^\s*OR\s*$", re.IGNORECASE)

def extract_marks_extended(text: str):
    match = MARKS_PATTERN.search(text)
    if match:
        for group in match.groups():
            if group is not None:
                return float(group)
    for line in text.splitlines():
        match2 = TRAILING_MARKS_CO_PATTERN.search(line)
        if match2:
            return float(match2.group(1))
    match3 = SECTION_MARKS_PATTERN.search(text)
    if match3:
        try:
            return float(match3.group(3)) / float(match3.group(2))
        except:
            return float(match3.group(1))
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
'''

content += new_patterns
file_path.write_text(content, 'utf-8')
print('Updated patterns.py')
