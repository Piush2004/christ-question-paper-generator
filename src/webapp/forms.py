"""Parse and validate the Generate form's fields before they reach pipeline.run(). Pure functions, no
Flask dependency: a malformed or out-of-range field becomes a reported error, never an uncaught
exception — the same CLI-facing override formats as scripts/generate_paper.py accept, but this form
is reachable over the internet once the app is hosted, so every numeric field is bounded and the
course/session/model identifiers are checked against known-safe sets rather than trusted verbatim."""

from __future__ import annotations

import re

from scripts.generate_paper import parse_sections
from src.webapp.catalog import CourseOption

MAX_SECTIONS = 10
MAX_ITEMS_PER_SECTION = 50
MAX_MARKS_PER_ITEM = 100.0
MAX_MARKS_TOTAL = 1000
MAX_DURATION_MINUTES = 600
MIN_BLOOM_LEVEL, MAX_BLOOM_LEVEL = 1, 6

ALLOWED_MODELS = frozenset({"qwen2.5:7b-instruct-q4_K_M"})

_SAFE_SESSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .\-]{1,39}$")


def build_overrides(form: dict[str, str]) -> tuple[dict, list[str]]:
    overrides: dict = {}
    errors: list[str] = []

    sections_raw = (form.get("sections") or "").strip()
    if sections_raw:
        try:
            specs = parse_sections(sections_raw)
        except (ValueError, IndexError):
            specs = None
            errors.append("Couldn't read the sections field — expected e.g. A:10x2,B:6x5:2")
        if specs is not None:
            section_errors = _validate_sections(specs)
            if section_errors:
                errors.extend(section_errors)
            else:
                overrides["sections"] = specs

    bloom_raw = (form.get("bloom") or "").strip()
    if bloom_raw:
        try:
            bloom_target = {
                int(k.strip().lstrip("Ll")): float(v)
                for k, v in (part.split(":") for part in bloom_raw.split(","))
            }
        except ValueError:
            bloom_target = None
            errors.append("Couldn't read the Bloom targets field — expected e.g. 2:0.3,3:0.4,4:0.3")
        if bloom_target is not None:
            bloom_errors = _validate_bloom_target(bloom_target)
            if bloom_errors:
                errors.extend(bloom_errors)
            else:
                overrides["bloom_target"] = bloom_target

    max_marks_raw = (form.get("max_marks") or "").strip()
    if max_marks_raw:
        try:
            max_marks = int(max_marks_raw)
            if not (1 <= max_marks <= MAX_MARKS_TOTAL):
                raise ValueError
        except ValueError:
            errors.append(f"Max marks must be a whole number between 1 and {MAX_MARKS_TOTAL}.")
        else:
            overrides["max_marks"] = max_marks

    duration_raw = (form.get("duration") or "").strip()
    if duration_raw:
        try:
            duration = int(duration_raw)
            if not (1 <= duration <= MAX_DURATION_MINUTES):
                raise ValueError
        except ValueError:
            errors.append(f"Duration must be a whole number of minutes, up to {MAX_DURATION_MINUTES}.")
        else:
            overrides["duration_minutes"] = duration

    return overrides, errors


def _validate_sections(specs: list) -> list[str]:
    errors: list[str] = []
    if len(specs) > MAX_SECTIONS:
        errors.append(f"Too many sections (max {MAX_SECTIONS}).")
        return errors
    for s in specs:
        if not (1 <= s.n_items <= MAX_ITEMS_PER_SECTION):
            errors.append(f"Section {s.label}: item count must be between 1 and {MAX_ITEMS_PER_SECTION}.")
        if not (0 < s.marks_each <= MAX_MARKS_PER_ITEM):
            errors.append(f"Section {s.label}: marks per item must be between 0 and {MAX_MARKS_PER_ITEM:g}.")
        if not (0 <= s.n_choice <= s.n_items):
            errors.append(f"Section {s.label}: choice items can't exceed the section's total items.")
    return errors


def _validate_bloom_target(bloom_target: dict[int, float]) -> list[str]:
    errors: list[str] = []
    for level, share in bloom_target.items():
        if not (MIN_BLOOM_LEVEL <= level <= MAX_BLOOM_LEVEL):
            errors.append(f"Bloom level {level} is out of range (must be {MIN_BLOOM_LEVEL}-{MAX_BLOOM_LEVEL}).")
        if not (0 < share <= 1):
            errors.append(f"Bloom share for level {level} must be between 0 and 1.")
    return errors


def validate_course_and_session(course: str, session: str, known_courses: list[CourseOption]) -> list[str]:
    errors: list[str] = []
    valid_identifiers = {c.code for c in known_courses} | {c.family for c in known_courses}
    if course not in valid_identifiers:
        errors.append("Unknown course — choose one from the list.")
    if not _SAFE_SESSION.match(session):
        errors.append(
            "Exam session may only contain letters, numbers, spaces, '.' and '-' (2-40 characters)."
        )
    return errors


def validate_model(model: str) -> list[str]:
    if model not in ALLOWED_MODELS:
        return [f"'{model}' is not an approved model. Allowed: {', '.join(sorted(ALLOWED_MODELS))}."]
    return []
