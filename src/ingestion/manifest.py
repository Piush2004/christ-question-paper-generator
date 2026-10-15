"""Dataset inventory / manifest builder (master-prompt §8, hardened per Phase 0.5 §7).

Scans a directory of raw source documents and produces one row per file with the inventory fields
the master prompt requires (filename, format, size, page count, scanned-vs-text, extraction quality),
plus the provenance/versioning fields Phase 0.5 requires: a stable content-hash `document_id` (so the
same paper can never silently appear as two different dataset entries even if renamed), an `origin`
tag (fixture/synthetic/real/evaluation — never let synthetic fixture data pass as real), and a
`processing_status` that a downstream quality gate can act on.

Academic year / course / subject / semester / program are NOT guessed from filenames by pattern
matching that could silently misassign metadata — they are left blank here for a human/config-driven
fill-in step, per Rule 4 (never hide failures) and §8 ("do not fabricate missing labels", stated for
annotation but applied here defensively to document metadata too). A best-effort filename parser can
be added once real filenames are seen and a naming convention is confirmed with the source institution.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from src.ingestion.exceptions import DocumentLoadError, UnsupportedFormatError
from src.ingestion.loaders import load_document
from src.ingestion.validation import validate_file

MANIFEST_COLUMNS = [
    "document_id",
    "filename",
    "format",
    "size_bytes",
    "sha256",
    "origin",
    "academic_year",
    "program",
    "semester",
    "course",
    "subject",
    "source",
    "file_modified_at",
    "page_count",
    "scanned_or_text",
    "pages_needing_ocr",
    "extraction_quality",
    "processing_status",
    "is_valid",
    "validation_errors",
    "duplicate_of",
]


class ProcessingStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    OCR_REQUIRED = "ocr_required"


class Origin(StrEnum):
    """Distinguishes real institutional data from anything that must never be mistaken for it
    (Phase 0.5 §14 — fixture/synthetic data must never leak into a training dataset)."""

    REAL = "real"
    FIXTURE = "fixture"
    SYNTHETIC = "synthetic"
    EVALUATION = "evaluation"


@dataclass
class ManifestRow:
    document_id: str | None  # stable content-hash id; None only when the file couldn't be hashed at all
    filename: str
    format: str
    size_bytes: int
    sha256: str | None
    origin: str
    academic_year: str | None
    program: str | None
    semester: str | None
    course: str | None
    subject: str | None
    source: str  # always populated (str(path)) in every code path below — never actually optional
    file_modified_at: str | None  # ISO 8601
    page_count: int
    scanned_or_text: str  # "text" | "scanned" | "mixed" | "unknown"
    pages_needing_ocr: int
    extraction_quality: float  # fraction of pages with usable extracted text, 0.0-1.0
    processing_status: str
    is_valid: bool
    validation_errors: str  # semicolon-joined for CSV-friendliness
    duplicate_of: str | None  # filename of the first file seen with the same sha256, if any


def build_manifest(raw_dir: Path, origin: Origin | str = Origin.REAL) -> list[ManifestRow]:
    origin = Origin(origin)
    rows: list[ManifestRow] = []
    if not raw_dir.exists():
        raise FileNotFoundError(f"raw_dir does not exist: {raw_dir}")

    seen_hashes: dict[str, str] = {}  # sha256 -> filename of first occurrence
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".docx", ".txt"}:
            continue
        row = _manifest_row_for(path, origin)
        if row.sha256 is not None:
            if row.sha256 in seen_hashes:
                row.duplicate_of = seen_hashes[row.sha256]
            else:
                seen_hashes[row.sha256] = row.filename
        rows.append(row)
    return rows


def _manifest_row_for(path: Path, origin: Origin) -> ManifestRow:
    validation = validate_file(path)
    file_modified_at = (
        datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        if path.is_file()
        else None
    )
    document_id = validation.sha256[:16] if validation.sha256 else None

    if not validation.is_valid:
        return ManifestRow(
            document_id=document_id,
            filename=path.name,
            format=path.suffix.lower().lstrip("."),
            size_bytes=validation.file_size_bytes,
            sha256=validation.sha256,
            origin=origin.value,
            academic_year=None,
            program=None,
            semester=None,
            course=None,
            subject=None,
            source=str(path),
            file_modified_at=file_modified_at,
            page_count=0,
            scanned_or_text="unknown",
            pages_needing_ocr=0,
            extraction_quality=0.0,
            processing_status=ProcessingStatus.INVALID.value,
            is_valid=False,
            validation_errors="; ".join(validation.errors),
            duplicate_of=None,
        )

    # A file can pass validate_file()'s cheap checks (extension, size, PDF magic bytes) yet still
    # fail to actually parse (corrupt/truncated/encrypted). That must be a controlled per-file
    # failure recorded in the manifest, not an exception that aborts the entire directory scan.
    try:
        doc = load_document(path)
    except (DocumentLoadError, UnsupportedFormatError) as exc:
        return ManifestRow(
            document_id=document_id,
            filename=path.name,
            format=path.suffix.lower().lstrip("."),
            size_bytes=validation.file_size_bytes,
            sha256=validation.sha256,
            origin=origin.value,
            academic_year=None,
            program=None,
            semester=None,
            course=None,
            subject=None,
            source=str(path),
            file_modified_at=file_modified_at,
            page_count=0,
            scanned_or_text="unknown",
            pages_needing_ocr=0,
            extraction_quality=0.0,
            processing_status=ProcessingStatus.INVALID.value,
            is_valid=False,
            validation_errors=str(exc),
            duplicate_of=None,
        )

    page_count = len(doc.pages)
    needing_ocr = len(doc.pages_needing_ocr)
    if page_count == 0:
        scanned_or_text = "unknown"
        quality = 0.0
    elif needing_ocr == 0:
        scanned_or_text = "text"
        quality = 1.0
    elif needing_ocr == page_count:
        scanned_or_text = "scanned"
        quality = 0.0
    else:
        scanned_or_text = "mixed"
        quality = round(1 - (needing_ocr / page_count), 4)

    processing_status = ProcessingStatus.OCR_REQUIRED if needing_ocr > 0 else ProcessingStatus.VALID

    return ManifestRow(
        document_id=document_id,
        filename=path.name,
        format=path.suffix.lower().lstrip("."),
        size_bytes=validation.file_size_bytes,
        sha256=validation.sha256,
        origin=origin.value,
        academic_year=None,
        program=None,
        semester=None,
        course=None,
        subject=None,
        source=str(path),
        file_modified_at=file_modified_at,
        page_count=page_count,
        scanned_or_text=scanned_or_text,
        pages_needing_ocr=needing_ocr,
        extraction_quality=quality,
        processing_status=processing_status.value,
        is_valid=True,
        validation_errors="",
        duplicate_of=None,
    )


def write_manifest_csv(rows: list[ManifestRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
