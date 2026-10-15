"""Typed ingestion errors — every failure mode must be a controlled, specific exception, never a
raw crash or a silently-swallowed empty result (Phase 0.5 hardening §3: "Every failure must produce
a controlled error, not a crash")."""

from __future__ import annotations


class DocumentLoadError(RuntimeError):
    """Raised when a file passes validate_file() but fails to actually parse (corrupt/truncated)."""


class EncryptedDocumentError(DocumentLoadError):
    """Raised when a PDF is password-protected and cannot be read without a password."""


class UnsupportedFormatError(ValueError):
    """Raised when load_document() is given an extension outside SUPPORTED_EXTENSIONS."""
