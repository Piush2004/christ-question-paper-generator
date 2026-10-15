from pathlib import Path
import re

content = Path('src/extraction/patterns.py').read_text('utf-8')
content = content.replace(r'"\\\\b(\\\\d+)\\\\s*[\\\\*xX]\\\\s*(\\\\d+)\\\\s*=\\\\s*(\\\\d+)\\\\b"', 
                          r'"\\\\b(\\\\d+)\\\\s*[\\\\*xX×]\\\\s*(\\\\d+)\\\\s*=\\\\s*(\\\\d+)\\\\b"')
Path('src/extraction/patterns.py').write_text(content, 'utf-8')
