"""Dataset versioning (Phase 0.5 §8/§9).

A dataset version is a deterministic content hash over every scanned file's identity (document_id +
validity), not an incrementing counter. This is the simplest design that satisfies both requirements
at once:

  - Idempotency (§9): running the same ingest twice over unchanged files produces the exact same
    version id — no mutable counter state to accidentally bump, no risk of "run twice, get v2 both
    times" drift.
  - Versioning (§8): adding, removing, or replacing any file changes the id immediately, so a future
    experiment can always name exactly which set of documents it was trained against.

`data/dataset_versions.json` is an append-only, dedup-by-version-id log — a human-readable history of
every distinct dataset state ever observed, without needing a database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.ingestion.manifest import ManifestRow


def compute_dataset_version(rows: list[ManifestRow]) -> str:
    """Deterministic id over the set of documents in this manifest. Two runs over the same files
    (even in different scan order, even with different mtimes) yield the same id — only file
    *content* (via sha256) and *validity* affect it, not filesystem metadata or scan order."""
    identity_tokens = sorted(
        f"{row.sha256 or 'nohash'}:{row.is_valid}" for row in rows
    )
    digest = hashlib.sha256("|".join(identity_tokens).encode("utf-8")).hexdigest()
    return f"v_{digest[:16]}"


@dataclass
class DatasetVersionRecord:
    version_id: str
    created_at: str  # ISO 8601, of when this version was FIRST observed
    file_count: int
    valid_count: int
    invalid_count: int


def record_dataset_version(rows: list[ManifestRow], versions_log_path: Path,
                            now: datetime | None = None) -> DatasetVersionRecord:
    """Append this version to the log only if it hasn't been seen before (dedup by version_id —
    the idempotency guarantee). Returns the record for this version, whether newly created or
    pre-existing."""
    version_id = compute_dataset_version(rows)
    now = now or datetime.now(UTC)

    history = _load_versions(versions_log_path)
    existing = next((v for v in history if v.version_id == version_id), None)
    if existing is not None:
        return existing

    record = DatasetVersionRecord(
        version_id=version_id,
        created_at=now.isoformat(),
        file_count=len(rows),
        valid_count=sum(1 for r in rows if r.is_valid),
        invalid_count=sum(1 for r in rows if not r.is_valid),
    )
    history.append(record)
    _write_versions(versions_log_path, history)
    return record


def _load_versions(path: Path) -> list[DatasetVersionRecord]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [DatasetVersionRecord(**entry) for entry in raw]


def _write_versions(path: Path, history: list[DatasetVersionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(v) for v in history], indent=2),
        encoding="utf-8",
    )
