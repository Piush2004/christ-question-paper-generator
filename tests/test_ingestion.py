from pathlib import Path

import pytest
from docx import Document as DocxDocument
from fpdf import FPDF

from src.ingestion.loaders import load_document
from src.ingestion.manifest import Origin, build_manifest
from src.ingestion.validation import validate_file

FIXTURES = Path(__file__).parent / "fixtures"


# --- validation ---

def test_validate_file_missing():
    result = validate_file(Path("does_not_exist.pdf"))
    assert not result.is_valid
    assert "does not exist" in result.errors[0]


def test_validate_file_unsupported_extension(tmp_path: Path):
    bad = tmp_path / "paper.xlsx"
    bad.write_text("x" * 100)
    result = validate_file(bad)
    assert not result.is_valid
    assert any("Unsupported extension" in e for e in result.errors)


def test_validate_file_too_small(tmp_path: Path):
    tiny = tmp_path / "tiny.txt"
    tiny.write_text("hi")
    result = validate_file(tiny)
    assert not result.is_valid
    assert any("too small" in e for e in result.errors)


def test_validate_file_fake_pdf_magic_bytes(tmp_path: Path):
    fake = tmp_path / "fake.pdf"
    fake.write_text("this is not really a pdf but is long enough to pass size check")
    result = validate_file(fake)
    assert not result.is_valid
    assert any("%PDF-" in e for e in result.errors)


def test_validate_file_valid_txt():
    result = validate_file(FIXTURES / "sample_simple.txt")
    assert result.is_valid
    assert result.sha256 is not None
    assert result.file_size_bytes > 0


# --- loaders ---

def test_load_txt():
    doc = load_document(FIXTURES / "sample_simple.txt")
    assert len(doc.pages) == 1
    assert "Q1." in doc.full_text
    assert doc.pages_needing_ocr == []


def test_load_docx(tmp_path: Path):
    path = tmp_path / "sample.docx"
    docx = DocxDocument()
    docx.add_paragraph("Q1. What is gradient descent? [10]")
    docx.add_paragraph("Q2. Define entropy. [5]")
    docx.save(str(path))

    doc = load_document(path)
    assert len(doc.pages) == 1
    assert "Q1." in doc.full_text
    assert "Q2." in doc.full_text


def test_load_pdf_text_native(tmp_path: Path):
    path = tmp_path / "sample.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Q1. Explain overfitting. [10]")
    pdf.output(str(path))

    doc = load_document(path)
    assert len(doc.pages) == 1
    assert "overfitting" in doc.full_text.lower()
    assert doc.pages[0].needs_ocr is False


def test_load_pdf_blank_page_flagged_needs_ocr(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.output(str(path))

    doc = load_document(path)
    assert len(doc.pages) == 1
    assert doc.pages[0].needs_ocr is True
    assert doc.pages_needing_ocr == [1]


# --- manifest ---

def test_build_manifest_over_fixtures_dir():
    rows = build_manifest(FIXTURES, origin=Origin.FIXTURE)
    filenames = {r.filename for r in rows}
    assert "sample_simple.txt" in filenames
    assert "sample_sections.txt" in filenames
    for row in rows:
        assert row.is_valid
        assert row.page_count >= 1
        assert row.scanned_or_text == "text"
        assert row.extraction_quality == 1.0
        assert row.origin == Origin.FIXTURE
        assert row.document_id is not None


def test_build_manifest_missing_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        build_manifest(tmp_path / "nope")
