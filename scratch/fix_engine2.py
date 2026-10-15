import sys
from pathlib import Path
import re

file_path = Path('src/extraction/engine.py')
content = file_path.read_text('utf-8')

content = content.replace(
    'number = top_m.group(1) or top_m.group(2)',
    'number = top_m.group(1) or top_m.group(2) or top_m.group(3)'
)

file_path.write_text(content, 'utf-8')
print('Fixed engine.py group 3')
