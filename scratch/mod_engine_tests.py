
from pathlib import Path

content = Path('src/extraction/engine.py').read_text('utf-8')
old = '''            else:
                for text_line in page.text.splitlines():
                    if text_line.strip():
                        lines.append(_Line(text=text_line, page_number=page.page_number, y0=0.0))'''
new = '''            else:
                dummy_y = 0.0
                for text_line in page.text.splitlines():
                    if text_line.strip():
                        lines.append(_Line(text=text_line, page_number=page.page_number, y0=dummy_y))
                        dummy_y += 10.0'''
content = content.replace(old, new)
Path('src/extraction/engine.py').write_text(content, 'utf-8')
