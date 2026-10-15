import re
from pathlib import Path

content = Path('src/extraction/engine.py').read_text('utf-8')
# Lines 52 and 74 have broken literals: alt_text = "\\n".join...
content = re.sub(r'alt_text = "\n"\.join', 'alt_text = "\\\\n".join', content)
Path('src/extraction/engine.py').write_text(content, 'utf-8')
