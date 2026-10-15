import sys
from pathlib import Path
import re

file_path = Path('src/extraction/patterns.py')
content = file_path.read_text('utf-8')

content = content.replace(
    r'"^\s*(?:(?:Q(?:uestion)?\.?\s*)(\d{1,3})\b\.?|(\d{1,3})[.)]?(?:\s+|$))"',
    r'"^\s*(?:(?:Q(?:uestion)?\.?\s*)(\d{1,3})\b\.?|(\d{1,3})[.)](?:\s+|$)|(\d{1,3})\s*$)"'
)

file_path.write_text(content, 'utf-8')
print('Updated TOP_LEVEL_QUESTION again')
