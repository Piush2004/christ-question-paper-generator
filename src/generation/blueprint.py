"""Assessment blueprint: the teacher's structured request, validated *before* any model is called.

A blueprint fixes everything the paper format needs (sections, items per section, marks per item, how
many items carry an OR alternative) plus the cognitive targets (RBT level mix) and curriculum targets
(course-outcome coverage). `Blueprint.validate()` returns human-readable problems; the allocator and
generator refuse to run on an invalid blueprint — a paper is never silently produced from
contradictory constraints.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STANDARD_INSTRUCTIONS = [
    "All rough work should be done in the answer script. Do not write or scribble in the question paper "
    "except your register number.",
    "Verify the Course code / course title and number of pages of questions in the question paper.",
    "Make sure your mobile phone is switched off and placed at the designated place.",
    "Malpractices will be viewed very seriously.",
    "Answers should be written on both sides of the paper in the answer book. No sheets should be detached "
    "from the answer book.",
    "Answers without the question numbers clearly indicated will not be valued. No page should be left blank "
    "in the middle of the answer book.",
]
SEMESTER_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
RBT_LEGEND = ["L1 - Remember", "L2 - Understand", "L3 - Apply", "L4 - Analyse", "L5 - Evaluate", "L6 - Create"]


@dataclass
class SectionSpec:
    label: str
    n_items: int
    marks_each: float
    n_choice: int = 0                       # items that carry an "a) ... OR b) ..." pair
    instruction: str = "Answer all the questions"

    @property
    def total_marks(self) -> float:
        return self.n_items * self.marks_each

    @property
    def n_questions(self) -> int:           # questions that must actually be written
        return self.n_items + self.n_choice

    @property
    def spec_line(self) -> str:             # printed as "2*10=20"
        return f"{self.marks_each:g}*{self.n_items}={self.total_marks:g}"


@dataclass
class Blueprint:
    course_code: str
    course_name: str
    semester: int
    exam_session: str                        # "November 2025"
    max_marks: int
    duration_minutes: int
    outcomes: dict[str, str]
    sections: list[SectionSpec]
    syllabus_year: str = ""
    program: str = "Bachelor of Computer Applications"
    exam_title: str = "End Semester Examinations"
    # Cognitive target: share of *marks* at each RBT level (L1..L6). None => learned from history.
    bloom_target: dict[int, float] | None = None
    # Course-outcome target: share of marks per CO. None => learned from history.
    co_weights: dict[str, float] | None = None
    # How strongly to follow historical topic frequency (1) vs. spread over under-asked topics (0).
    history_weight: float = 0.5
    novelty_max_similarity: float = 0.80    # candidate rejected if cosine similarity to history exceeds this
    candidates_per_slot: int = 4
    seed: int = 7
    notes: str = ""
    allow_broader_than_history: bool = False

    # ----------------------------------------------------------------------------------- checks
    def validate(self) -> list[str]:
        problems: list[str] = []
        total = sum(s.total_marks for s in self.sections)
        if abs(total - self.max_marks) > 1e-6:
            problems.append(f"Sections add up to {total:g} marks but Max Marks is {self.max_marks}. "
                            f"Adjust items/marks per section so they sum to {self.max_marks}.")
        labels = [s.label for s in self.sections]
        if len(set(labels)) != len(labels):
            problems.append("Section labels must be unique.")
        for s in self.sections:
            if s.n_items <= 0 or s.marks_each <= 0:
                problems.append(f"Section {s.label}: items and marks per item must be positive.")
            if s.n_choice > s.n_items:
                problems.append(f"Section {s.label}: {s.n_choice} choice (OR) items but only {s.n_items} items.")
        if not self.outcomes:
            problems.append("No course outcomes (COs) are available for this course — add them before generating.")
        n_items = sum(s.n_items for s in self.sections)
        if self.outcomes and n_items < len(self.outcomes):
            problems.append(f"{n_items} questions cannot cover all {len(self.outcomes)} course outcomes; "
                            "increase the question count or drop outcomes from the blueprint.")
        if self.bloom_target is not None:
            if any(k not in range(1, 7) for k in self.bloom_target):
                problems.append("Bloom targets must use levels 1-6.")
            tot = sum(self.bloom_target.values())
            if abs(tot - 1.0) > 0.01:
                problems.append(f"Bloom target shares add up to {tot:.2f}, not 1.00.")
        if self.co_weights is not None:
            unknown = set(self.co_weights) - set(self.outcomes)
            if unknown:
                problems.append(f"co_weights mention unknown outcomes: {sorted(unknown)}")
        return problems

    @property
    def n_questions(self) -> int:
        return sum(s.n_questions for s in self.sections)

    @property
    def header_title(self) -> str:
        return f"{self.exam_title} - {self.exam_session}"

    @property
    def semester_roman(self) -> str:
        return SEMESTER_ROMAN.get(self.semester, str(self.semester))

    def to_json(self) -> str:
        d = json.loads(json.dumps(self, default=lambda o: o.__dict__))
        return json.dumps(d, indent=2)


def load_papers() -> list[dict]:
    f = ROOT / "data" / "processed" / "papers.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]


def family_of(course_code_or_family: str, papers: list[dict]) -> str:
    for p in papers:
        if p["course_code"] == course_code_or_family:
            return p["course_family"]
    if any(p["course_family"] == course_code_or_family for p in papers):
        return course_code_or_family
    raise ValueError(f"Unknown course '{course_code_or_family}'. Known: "
                     f"{sorted({p['course_code'] for p in papers})} or families {sorted({p['course_family'] for p in papers})}")


def load_questions() -> list[dict]:
    f = ROOT / "data" / "processed" / "questions.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]


def default_blueprint(course_code: str, exam_session: str, *, papers: list[dict] | None = None,
                      questions: list[dict] | None = None, before_session_of: str | None = None,
                      family: str | None = None) -> Blueprint:
    """Build a blueprint mirroring the structure of the course's most recent paper.

    `before_session_of`: if given, only papers strictly older than that paper id are considered
    (used by the held-out evaluation so structure is never read from the paper being predicted).
    """
    papers = papers if papers is not None else load_papers()
    questions = questions if questions is not None else load_questions()
    # A subject keeps its identity across years even when its code changes (e.g. Discrete Mathematics is
    # BCA104-2 in 2024 and BCA101-2 in 2025), so papers are grouped by subject family, not by code.
    fam = family or family_of(course_code, papers)
    cands = [p for p in papers if p["course_family"] == fam]
    if before_session_of:
        cutoff = next(p for p in papers if p["paper_id"] == before_session_of)
        cands = [p for p in cands if p["academic_year"] < cutoff["academic_year"]
                 or (p["academic_year"] == cutoff["academic_year"] and p["paper_id"] != cutoff["paper_id"]
                     and _session_order(p["exam_session"]) < _session_order(cutoff["exam_session"]))]
    if not cands:
        raise ValueError(f"No historical paper found for course {course_code}")
    cands.sort(key=lambda p: (p["academic_year"], _session_order(p["exam_session"])))
    latest = cands[-1]
    qs = [q for q in (questions or []) if q["paper_id"] == latest["paper_id"]]
    sections = []
    for s in latest["sections"]:
        n_choice = len({q["number"] for q in qs if q["section"] == s["label"] and q["kind"] == "alt"}) if qs else 0
        sections.append(SectionSpec(label=s["label"], n_items=int(s["questions_to_answer"] or s["items_listed"]),
                                    marks_each=float(s["marks_per_question"]), n_choice=n_choice,
                                    instruction="Answer all the questions"))
    year = latest["academic_year"] or ""
    return Blueprint(
        course_code=latest["course_code"], course_name=(latest["course_name"] or "").upper(),
        semester=int(latest["semester"] or 1), exam_session=exam_session, max_marks=int(latest["max_marks"]),
        duration_minutes=int(latest["duration_minutes"] or 180), outcomes=dict(latest["outcomes"]),
        sections=sections, syllabus_year=year_label(year),
    )


def _session_order(session: str | None) -> int:
    s = (session or "").lower()
    return 0 if "nov" in s or "dec" in s or "oct" in s else 1   # odd-semester (Nov) precedes even (Apr/May) within a year


def year_label(academic_year: str) -> str:
    if academic_year and "-" in academic_year:
        a, b = academic_year.split("-")
        return f"{a}-20{b}" if len(b) == 2 else academic_year
    return academic_year
