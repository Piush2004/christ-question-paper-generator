
from pathlib import Path

content = Path('tests/test_phase1a.py').read_text('utf-8')
new_test = '''
def test_spatial_layout_section_assignment():
    from src.extraction.engine import _Line, _Marker
    # Manually construct lines with out-of-order text but proper spatial coordinates
    # to simulate cn2024.pdf's disordered object stream.
    lines = [
        _Line(page_number=1, text='1. Define entropy.', y0=100.0),
        _Line(page_number=1, text='2. Define perplexity.', y0=200.0),
        _Line(page_number=1, text='SECTION A', y0=50.0),   # Appears physically before Q1
        _Line(page_number=1, text='SECTION B', y0=150.0),  # Appears physically between Q1 and Q2
    ]
    from src.extraction.engine import QuestionExtractor
    extractor = QuestionExtractor()
    markers = extractor._classify_lines(lines)
    extractor._assign_spans(markers, lines)
    qs = extractor._build_hierarchy(markers)
    
    assert len(qs) == 2
    assert qs[0].question_number_raw == '1'
    assert qs[0].section_label == 'SECTION A'
    
    assert qs[1].question_number_raw == '2'
    assert qs[1].section_label == 'SECTION B'
'''
content += new_test
Path('tests/test_phase1a.py').write_text(content, 'utf-8')
