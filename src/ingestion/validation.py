"""File-level validation gate — the first stage of the ingestion pipeline (master-prompt §9).

Fails loudly and specifically rather than letting a bad file silently produce empty/garbage
downstream output (Rule 4: never hide failures).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MIN_FILE_SIZE_BYTES = 16  # anything smaller cannot possibly contain a real question


@dataclass
class ValidationResult:
    path: Path
    is_valid: bool
    file_size_bytes: int
    sha256: str | None
    errors: list[str] = field(default_factory=list)


def validate_file(path: Path) -> ValidationResult:
    errors: list[str] = []

    if not path.exists():
        return ValidationResult(path=path, is_valid=False, file_size_bytes=0, sha256=None,
                                 errors=[f"File does not exist: {path}"])

    if not path.is_file():
        errors.append(f"Path is not a regular file: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        errors.append(
            f"Unsupported extension '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    size = path.stat().st_size if path.is_file() else 0
    if size < MIN_FILE_SIZE_BYTES:
        errors.append(f"File too small ({size} bytes) to plausibly contain content")

    sha256 = _sha256(path) if path.is_file() and size >= MIN_FILE_SIZE_BYTES else None

    if ext == ".pdf" and path.is_file() and size >= MIN_FILE_SIZE_BYTES:
        header = path.read_bytes()[:5]
        if header != b"%PDF-":
            errors.append("File has .pdf extension but does not start with the %PDF- magic bytes")

    return ValidationResult(
        path=path,
        is_valid=len(errors) == 0,
        file_size_bytes=size,
        sha256=sha256,
        errors=errors,
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
