"""Adversarial ingestion tests (Phase 0.5 hardening §3, §10).

Every malformed-input case must raise a specific, typed, controlled error — never a raw crash,
never silent empty output.
"""

from pathlib import Path

import pymupdf as fitz
import pytest
from fpdf import FPDF

from src.ingestion.exceptions import (
    DocumentLoadError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)
from src.ingestion.loaders import load_document
from src.ingestion.manifest import Origin, build_manifest


def test_corrupt_pdf_raises_document_load_error(tmp_path: Path):
    # Passes validate_file()'s %PDF- magic-byte check but is not a real PDF structure.
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\n" + b"this is not a valid pdf body" * 10)

    with pytest.raises(DocumentLoadError):
        load_document(path)


def test_password_protected_pdf_raises_encrypted_document_error(tmp_path: Path):
    path = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    doc.new_page()
    doc[0].insert_text((72, 72), "Q1. Secret question. [10]")
    doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user123")  # type: ignore[attr-defined]  # pymupdf stub gap; constant exists at runtime
    doc.close()

    with pytest.raises(EncryptedDocumentError):
        load_document(path)


def test_corrupt_docx_raises_document_load_error(tmp_path: Path):
    path = tmp_path / "corrupt.docx"
    # A .docx is a zip; this is not a zip at all.
    path.write_bytes(b"not a real docx file, just plain bytes padded to be long enough")

    with pytest.raises(DocumentLoadError):
        load_document(path)


def test_unsupported_extension_raises_unsupported_format_error(tmp_path: Path):
    path = tmp_path / "paper.xlsx"
    path.write_bytes(b"x" * 100)

    with pytest.raises(UnsupportedFormatError):
        load_document(path)


def test_blank_pdf_loads_with_zero_usable_text_not_a_crash(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.output(str(path))

    doc = load_document(path)
    assert doc.pages[0].needs_ocr is True


# --- manifest-level: one bad file must not abort the whole scan (controlled per-file failure) ---

def test_manifest_scan_survives_one_corrupt_file_among_valid_ones(tmp_path: Path):
    good = tmp_path / "good.txt"
    good.write_text("Q1. A valid question. [5]\n")

    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\n" + b"garbage not a real pdf" * 10)

    rows = build_manifest(tmp_path, origin=Origin.FIXTURE)
    by_name = {r.filename: r for r in rows}

    assert by_name["good.txt"].is_valid is True
    assert by_name["corrupt.pdf"].is_valid is False
    assert "corrupt" in by_name["corrupt.pdf"].validation_errors.lower() or \
        by_name["corrupt.pdf"].validation_errors != ""


def test_manifest_scan_survives_encrypted_file(tmp_path: Path):
    encrypted = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    doc.new_page()
    doc[0].insert_text((72, 72), "Q1. Secret. [10]")
    doc.save(str(encrypted), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user123")  # type: ignore[attr-defined]  # pymupdf stub gap; constant exists at runtime
    doc.close()

    rows = build_manifest(tmp_path, origin=Origin.FIXTURE)
    row = rows[0]
    assert row.is_valid is False
    assert "password" in row.validation_errors.lower() or "encrypt" in row.validation_errors.lower()
