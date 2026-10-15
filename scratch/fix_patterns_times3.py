from pathlib import Path
import re
import codecs

content = Path('src/extraction/patterns.py').read_text('utf-8')
content = content.replace(r'[\*xX]', r'[\*xX\u00d7\ufffd]')
content = content.replace(r'[\*xX]', r'[\*xX\u00d7\ufffd]')
Path('src/extraction/patterns.py').write_text(content, 'utf-8')
