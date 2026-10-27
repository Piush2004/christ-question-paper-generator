"""Experimental-design safeguards: subject families never mix different courses, and every evaluation target's history
excludes the held-out paper."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "data" / "processed" / "papers.jsonl"
pytestmark = pytest.mark.skipif(not PAPERS.exists(), reason="dataset not built")


def papers():
    return [json.loads(l) for l in PAPERS.read_text(encoding="utf-8").splitlines()]


def test_a_family_is_one_course():
    fam_names = {}
    for p in papers():
        base = " ".join((p["course_name"] or "").lower().split())
        fam_names.setdefault(p["course_family"], set()).add(base)
    for fam, names in fam_names.items():
        assert len(names) == 1, f"family {fam} mixes different course names: {names}"


def test_foundational_and_discrete_maths_and_psd_parts_are_separate_families():
    fam = {p["course_name"]: p["course_family"] for p in papers()}
    assert fam["Foundational Mathematics"] != fam["Discrete Mathematics"]
    assert fam["Principles Of Software Development - I"] != fam["Principles Of Software Development - Ii"]


def test_course_family_handles_arabic_and_roman_psd_numerals():
    from scripts.build_dataset import course_family
    assert course_family("Principles Of Software Development – 2") == "psd_2"
    assert course_family("Principles Of Software Development - II") == "psd_2"
    assert course_family("Principles Of Software Development – 1") == "psd_1"
    assert course_family("Principles Of Software Development - I") == "psd_1"


def test_evaluation_targets_are_labelled_and_same_course_targets_have_history():
    from scripts.eval_generation import build_targets
    ps = papers()
    targets = build_targets(ps)
    assert targets
    for fam, held, hist_fam, kind in targets:
        assert kind in ("same_course_temporal", "related_course_transfer")
        if kind == "same_course_temporal":
            assert hist_fam == fam
            assert sum(p["course_family"] == fam for p in ps) >= 2
        else:
            assert hist_fam != fam                                   # explicitly a different course of the same series
        assert next(p for p in ps if p["paper_id"] == held)["course_family"] == fam
