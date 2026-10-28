"""Parse the Generate form's text fields into pipeline.run's bp_overrides dict. Pure function, no
Flask dependency: a malformed field becomes a reported error, never an uncaught exception reaching
the request handler — the same CLI-facing formats as scripts/generate_paper.py accept."""

from __future__ import annotations

from scripts.generate_paper import parse_sections


def build_overrides(form: dict[str, str]) -> tuple[dict, list[str]]:
    overrides: dict = {}
    errors: list[str] = []

    sections_raw = (form.get("sections") or "").strip()
    if sections_raw:
        try:
            overrides["sections"] = parse_sections(sections_raw)
        except (ValueError, IndexError):
            errors.append("Couldn't read the sections field — expected e.g. A:10x2,B:6x5:2")

    bloom_raw = (form.get("bloom") or "").strip()
    if bloom_raw:
        try:
            overrides["bloom_target"] = {
                int(k.strip().lstrip("Ll")): float(v)
                for k, v in (part.split(":") for part in bloom_raw.split(","))
            }
        except ValueError:
            errors.append("Couldn't read the Bloom targets field — expected e.g. 2:0.3,3:0.4,4:0.3")

    max_marks_raw = (form.get("max_marks") or "").strip()
    if max_marks_raw:
        try:
            overrides["max_marks"] = int(max_marks_raw)
        except ValueError:
            errors.append("Max marks must be a whole number.")

    duration_raw = (form.get("duration") or "").strip()
    if duration_raw:
        try:
            overrides["duration_minutes"] = int(duration_raw)
        except ValueError:
            errors.append("Duration must be a whole number of minutes.")

    return overrides, errors
