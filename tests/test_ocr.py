"""OCR abstraction tests (Phase 0.5 §10). Tesseract is confirmed NOT installed on this dev machine
(docs/ENVIRONMENT_AUDIT.md §3) — these tests assert the pipeline reports that state cleanly rather
than crashing or silently pretending OCR succeeded."""

from pathlib import Path

import pytest

from src.ingestion.ocr import (
    DEFAULT_PROVIDER,
    OCRStatus,
    OCRUnavailableError,
    TesseractOCRProvider,
    get_page_ocr_status,
    run_ocr,
)


def test_tesseract_confirmed_unavailable_on_this_machine():
    # This assertion documents current environment state (docs/ENVIRONMENT_AUDIT.md §3/§5).
    # If Tesseract is later installed, this test should be updated, not silently skipped.
    assert DEFAULT_PROVIDER.is_available() is False


def test_status_not_needed_when_page_has_text():
    assert get_page_ocr_status(needs_ocr=False) == OCRStatus.NOT_NEEDED


def test_status_unavailable_when_page_needs_ocr_but_no_provider():
    assert get_page_ocr_status(needs_ocr=True) == OCRStatus.OCR_UNAVAILABLE


def test_run_ocr_reports_unavailable_status_not_a_crash(tmp_path: Path):
    fake_pdf = tmp_path / "scanned.pdf"
    fake_pdf.write_bytes(b"%PDF-1.7\nfake")
    status, text = run_ocr(fake_pdf, page_number=1)
    assert status == OCRStatus.OCR_UNAVAILABLE
    assert text is None


def test_direct_provider_call_raises_typed_error_when_unavailable(tmp_path: Path):
    provider = TesseractOCRProvider()
    fake_pdf = tmp_path / "scanned.pdf"
    fake_pdf.write_bytes(b"%PDF-1.7\nfake")
    with pytest.raises(OCRUnavailableError, match="Tesseract"):
        provider.ocr_pdf_page(fake_pdf, 1)
