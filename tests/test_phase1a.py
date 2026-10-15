import pytest
from src.extraction.engine import QuestionExtractor
from src.ingestion.loaders import DocumentText, Page, PageTable

def test_extract_or_relationship():
    doc = DocumentText(
        source_path='dummy.pdf',
        pages=[Page(
            page_number=1,
            text='''6
Define edge chromatic number of a graph.
OR
State Euler’s formula.
CO3
L5
7
Next question...'''
        )]
    )
    qs = QuestionExtractor().extract(doc)
    assert len(qs) == 3 # 6, 6 (alt), 7
    assert qs[0].question_number_raw == '6'
    assert qs[0].is_alternative == False
    assert qs[0].raw_text == '6\nDefine edge chromatic number of a graph.'
    
    assert qs[1].question_number_raw == '6'
    assert qs[1].is_alternative == True
    assert 'State Euler’s formula.' in qs[1].raw_text
    assert qs[1].course_outcome == 'CO3'
    assert qs[1].bloom == 'L5'
    
    assert qs[2].question_number_raw == '7'

def test_extract_section_marks():
    doc = DocumentText(
        source_path='dummy.pdf',
        pages=[Page(
            page_number=1,
            text='''SECTION A (10 * 3 = 30 Marks)
1
What is a graph?
2
What is a tree?'''
        )]
    )
    qs = QuestionExtractor().extract(doc)
    assert len(qs) == 2
    assert qs[0].section_label == 'SECTION A (10 * 3 = 30 Marks)'
    assert qs[0].marks == 3.0
    
def test_extract_trailing_marks():
    doc = DocumentText(
        source_path='dummy.pdf',
        pages=[Page(
            page_number=1,
            text='''1) What is network?
2 (CO1, L1)'''
        )]
    )
    qs = QuestionExtractor().extract(doc)
    assert len(qs) == 1
    assert qs[0].marks == 2.0
    assert qs[0].course_outcome == 'CO1'
    assert qs[0].bloom == 'L1'

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
