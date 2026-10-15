"""OCR fallback for scanned PDF pages (master-prompt §9, hardened per Phase 0.5 §10).

`OCRProvider` is a clean abstraction boundary: today the only implementation is Tesseract (local,
free, already in requirements.txt), but nothing upstream depends on Tesseract specifically — a cloud
OCR provider could be swapped in later by implementing the same three methods. Every OCR attempt
reports one of the four states in `OCRStatus`, so the ingestion pipeline (and later the quality gate)
can always answer "what happened to this page" rather than silently treating missing text as "no
questions here."

Per the decision log entry "Deferred: OCR support blocked on missing system binary" — this module
fails loudly and specifically when the Tesseract binary is absent, rather than silently returning
empty text. Do not catch and suppress `TesseractNotFoundError`-style failures anywhere upstream.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path

import pymupdf as fitz
import pytesseract
from PIL import Image


class OCRStatus(StrEnum):
    OCR_REQUIRED = "ocr_required"      # page has too little embedded text; OCR would be needed
    OCR_UNAVAILABLE = "ocr_unavailable"  # OCR is required but no provider is available right now
    OCR_COMPLETED = "ocr_completed"    # OCR ran and returned text
    OCR_FAILED = "ocr_failed"          # OCR was attempted but the engine itself errored
    NOT_NEEDED = "not_needed"          # page already has usable embedded text; OCR was never invoked


class OCRUnavailableError(RuntimeError):
    """Raised when OCR is required but no provider is available on this machine."""


class OCRProvider(ABC):
    """Abstraction boundary so ingestion never hard-codes a specific OCR engine."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can currently perform OCR (e.g. binary installed, API reachable)."""

    @abstractmethod
    def ocr_pdf_page(self, pdf_path: Path, page_number: int, dpi: int = 300) -> str:
        """OCR a single 1-indexed page of a PDF. Raises OCRUnavailableError if not available."""


class TesseractOCRProvider(OCRProvider):
    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def ocr_pdf_page(self, pdf_path: Path, page_number: int, dpi: int = 300) -> str:
        if not self.is_available():
            raise OCRUnavailableError(
                "OCR was requested but the Tesseract OCR binary is not installed or not on PATH. "
                "This machine has pytesseract (the Python wrapper) but not the underlying engine. "
                "Install Tesseract for Windows (e.g. the UB-Mannheim build) and ensure `tesseract` "
                "resolves on PATH, or set pytesseract.pytesseract.tesseract_cmd explicitly. "
                "See docs/ENVIRONMENT_AUDIT.md §3/§5."
            )

        with fitz.open(pdf_path) as doc:
            if not (1 <= page_number <= doc.page_count):
                raise ValueError(f"page_number {page_number} out of range for {pdf_path} "
                                  f"(1..{doc.page_count})")
            page = doc[page_number - 1]
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        return pytesseract.image_to_string(image)


DEFAULT_PROVIDER = TesseractOCRProvider()


def tesseract_available() -> bool:
    """Kept for backward compatibility with existing callers; prefer DEFAULT_PROVIDER.is_available()."""
    return DEFAULT_PROVIDER.is_available()


def ocr_pdf_page(pdf_path: Path, page_number: int, dpi: int = 300) -> str:
    """Kept for backward compatibility; prefer calling a specific OCRProvider directly."""
    return DEFAULT_PROVIDER.ocr_pdf_page(pdf_path, page_number, dpi)


def get_page_ocr_status(needs_ocr: bool, provider: OCRProvider = DEFAULT_PROVIDER) -> OCRStatus:
    """Determine OCR status for a page WITHOUT attempting OCR (cheap, used by the manifest/quality
    gate to report readiness without doing the expensive OCR pass itself)."""
    if not needs_ocr:
        return OCRStatus.NOT_NEEDED
    if not provider.is_available():
        return OCRStatus.OCR_UNAVAILABLE
    return OCRStatus.OCR_REQUIRED


def run_ocr(pdf_path: Path, page_number: int, provider: OCRProvider = DEFAULT_PROVIDER,
            dpi: int = 300) -> tuple[OCRStatus, str | None]:
    """Actually attempt OCR, returning a (status, text) pair instead of raising for the
    "unavailable" / "failed" cases, since those are expected, common outcomes the caller must
    branch on — not exceptional. OCRUnavailableError is still raised for programmer-error cases
    (calling this without checking availability at all is fine; it degrades to a status, not a crash)."""
    if not provider.is_available():
        return OCRStatus.OCR_UNAVAILABLE, None
    try:
        text = provider.ocr_pdf_page(pdf_path, page_number, dpi)
    except OCRUnavailableError:
        return OCRStatus.OCR_UNAVAILABLE, None
    except Exception:  # noqa: BLE001 — any OCR engine failure is reported as a controlled status, not a crash
        return OCRStatus.OCR_FAILED, None
    return OCRStatus.OCR_COMPLETED, text
