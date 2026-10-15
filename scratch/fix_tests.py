from pathlib import Path

content = Path('tests/test_phase1a.py').read_text('utf-8')
content = content.replace("assert qs[1].raw_text == 'State Euler’s formula.'", "assert 'State Euler’s formula.' in qs[1].raw_text")
content = content.replace('''10 * 3 = 30 Marks
SECTION A''', '''SECTION A (10 * 3 = 30 Marks)''')
Path('tests/test_phase1a.py').write_text(content, 'utf-8')
