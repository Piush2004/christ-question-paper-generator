from pathlib import Path

content = Path('tests/test_phase1a.py').read_text('utf-8')
content = content.replace("assert qs[0].section_label == 'SECTION A'", "assert qs[0].section_label == 'SECTION A (10 * 3 = 30 Marks)'")
Path('tests/test_phase1a.py').write_text(content, 'utf-8')
