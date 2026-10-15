"""Layout-aware parser for CHRIST (Deemed to be University) end-semester question papers.

Why this exists next to the generic `QuestionExtractor`: the generic rule engine treats every
numbered line as a question marker, which on real papers invents "questions" out of table cells,
journal-entry numbers and trial-balance rows (see docs/PHASE_2_REAL_DATA_AUDIT.md). The real
papers follow one of two rigid institutional layouts, so a parser that *uses* that structure is
both more accurate and verifiable (marks must add up to the section totals printed on the paper).

Layouts handled
---------------
``terminator``  (current layout, Nov-2024 onwards)
    ``N)  question text ...`` followed by a terminator line ``<marks>  (CO<k>, L<j>)``.
    Choice is expressed as ``a) ... OR b) ...``; multi-part questions have several terminators.
    Section blocks are printed as ``<marks>*<count>=<total>`` + ``Section X``.
``table``       (Apr/May-2024 layout)
    A ``Q. No | Questions | CO | RBT`` table per section, with ``SECTION X`` headings and
    ``<count> X <marks> = <total>`` lines.

Everything extracted is verified against the paper itself (``ParsedPaper.warnings``): item count per
section, marks per section, presence of CO / RBT labels. A paper that fails verification is reported,
never silently accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], start=1)}

_TERMINATOR = re.compile(
    r"^(\d+(?:\.\d+)?)\s*\(\s*((?:CO\s*\d\s*,?\s*)+)\s*,?\s*((?:L\s*\d\s*,?\s*)+)\)\s*$", re.IGNORECASE)
_ITEM_START = re.compile(r"^(\d{1,2})\)\s*(.*)$")
_SPEC_NEW = re.compile(r"^(\d+)\s*\*\s*(\d+)\s*=\s*(\d+)$")
_SPEC_OLD = re.compile(r"(\d+)\s*[^\d=\s]{0,3}\s*(\d+)\s*=\s*(\d+)")
_SECTION = re.compile(r"^\s*section\s*[-:]?\s*([A-Z])\b", re.IGNORECASE)
_NOISE = re.compile(
    r"^(end[ -]sem(?:ester)?\s+examinations?\b.*|answer\s+(?:all|any)\b.*|ai-assisted draft\b.*|"
    r"revised bloom.*|l\d\s*[-–]\s*\w+.*)$", re.IGNORECASE)
_OR = re.compile(r"^\(?or\)?$", re.IGNORECASE)


@dataclass
class ParsedQuestion:
    number: int
    part: str | None           # "a"/"b" for alternatives and sub-parts, else None
    kind: str                  # "single" | "alt" | "part"
    text: str
    marks: float | None
    course_outcomes: list[str]
    rbt: list[str]             # e.g. ["L3"] or ["L4","L5"] (multi-label rows exist in real papers)
    section: str | None
    page: int


@dataclass
class ParsedSection:
    label: str                 # "A"
    marks_per_question: float | None
    questions_to_answer: int | None
    items_listed: int          # numbered questions printed in this section
    total_marks: float | None
    instruction: str | None = None


@dataclass
class ParsedPaper:
    file: str
    layout: str
    course_code: str | None = None
    course_name: str | None = None
    program: str | None = None
    semester: int | None = None
    department: str | None = None
    exam_title: str | None = None
    exam_session: str | None = None
    academic_year: str | None = None
    max_marks: int | None = None
    duration_minutes: int | None = None
    outcomes: dict[str, str] = field(default_factory=dict)
    sections: list[ParsedSection] = field(default_factory=list)
    questions: list[ParsedQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PaperParseError(ValueError):
    """The file cannot be read as a question paper at all (corrupt, encrypted, empty)."""


# --------------------------------------------------------------------------------------- helpers
def _clean(s: str) -> str:
    s = s.replace("\u200b", "").replace("\xa0", " ").replace("’", "'")
    return re.sub(r"[ \t]+", " ", s).strip()


def _labels(co_blob: str, l_blob: str) -> tuple[list[str], list[str]]:
    cos = [f"CO{n}" for n in re.findall(r"\d", co_blob)]
    rbt = [f"L{n}" for n in re.findall(r"\d", l_blob)]
    return cos, rbt


def _academic_year(month: int | None, year: int | None) -> str | None:
    if not month or not year:
        return None
    start = year if month >= 6 else year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _session(text: str) -> tuple[str | None, int | None, int | None]:
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)"
                  r"(?:\s*/\s*(?:may|june))?\s*(\d{4})", text, re.IGNORECASE)
    if not m:
        return None, None, None
    month = MONTHS[m.group(1).lower()]
    return f"{m.group(1).title()} {m.group(2)}", month, int(m.group(2))


def _header(lines: list[str], paper: ParsedPaper) -> None:
    blob = "\n".join(lines[:80])
    if m := re.search(r"Course Code:\s*([A-Z0-9-]+)", blob):
        paper.course_code = m.group(1)
    if m := re.search(r"Course Name:\s*(.+)", blob):
        paper.course_name = _clean(m.group(1)).title()
    if m := re.search(r"Max\.?\s*Marks:\s*(\d+)", blob):
        paper.max_marks = int(m.group(1))
    if m := re.search(r"Duration:\s*(\d+):(\d+)", blob):
        paper.duration_minutes = int(m.group(1)) * 60 + int(m.group(2))
    elif m := re.search(r"Time:\s*(\d+)\s*(?:hrs?|hours)", blob, re.IGNORECASE):
        paper.duration_minutes = int(m.group(1)) * 60
    if m := re.search(r"SEMESTER\s*-\s*([IVX]+)", blob):
        paper.semester = ROMAN.get(m.group(1))
    elif m := re.search(r"UG\s+([IVX]+)\s+Semester", blob, re.IGNORECASE):
        paper.semester = ROMAN.get(m.group(1).upper())
    if re.search(r"Bachelor of Computer Applications|Programme Name:\s*BCA", blob, re.IGNORECASE):
        paper.program = "BCA"
    if m := re.search(r"Department of ([A-Za-z ]+)", blob):
        paper.department = m.group(1).strip()
    for ln in lines[:10]:
        if re.search(r"examination", ln, re.IGNORECASE):
            paper.exam_title = ln
            break
    session, month, year = _session(blob)
    paper.exam_session, paper.academic_year = session, _academic_year(month, year)


def _outcomes(lines: list[str]) -> dict[str, str]:
    """Course outcomes: ``CO1: text`` possibly wrapped over several lines."""
    out: dict[str, str] = {}
    current: str | None = None
    for ln in lines[:120]:
        if re.match(r"^CO\s*\d\s*[.:]", ln):
            pieces = re.split(r"(?=\bCO\s*\d\s*[.:])", ln)
            for piece in filter(None, pieces):
                pm = re.match(r"^CO\s*(\d)\s*[.:]\s*(.*)$", piece.strip())
                if pm:
                    current = f"CO{pm.group(1)}"
                    out[current] = pm.group(2).strip()
        elif current and not (_ITEM_START.match(ln) or ln.lower().startswith(("answer", "section", "q.", "q "))
                              or re.match(r"^\d+\s+[A-Z]", ln) or re.match(r"^\d", ln)):
            if len(out[current]) < 400 and not re.match(r"^(general|course outcome)", ln, re.IGNORECASE):
                out[current] += " " + ln
        else:
            current = None if not ln.lower().startswith("course outcome") else current
        if _ITEM_START.match(ln) and out:
            break
    return {k: _clean(v) for k, v in out.items()}


# ------------------------------------------------------------------------------ terminator layout
def _parse_terminator(doc: pymupdf.Document, paper: ParsedPaper) -> None:
    raw_lines: list[tuple[int, str]] = []
    for pno, page in enumerate(doc, start=1):
        txt = _clean_page(page.get_text())
        # re-join terminators broken over two lines: "10 (CO3,\nL4)"
        txt = re.sub(r"(\(\s*CO\s*\d[^)\n]*,)\s*\n\s*(L\s*\d[^)\n]*\))", r"\1 \2", txt)
        # marks and "(CO, L)" printed on separate lines (table-style rendering) -> one terminator line
        txt = re.sub(r"(?m)^(\d+(?:\.\d+)?)[ \t]*\n[ \t]*(\(\s*CO\s*\d)", r"\1 \2", txt)
        for ln in txt.split("\n"):
            ln = _clean(ln)
            if ln:
                raw_lines.append((pno, ln))

    lines = [ln for _, ln in raw_lines]
    _header(lines, paper)
    paper.outcomes = _outcomes(lines)

    # section specs "2*10=20" immediately followed by "Section A"
    specs: list[tuple[str, int, int, int]] = []
    for i, (_, ln) in enumerate(raw_lines[:-1]):
        sm = _SPEC_NEW.match(ln)
        sec = _SECTION.match(raw_lines[i + 1][1])
        if sm and sec:
            specs.append((sec.group(1).upper(), int(sm.group(1)), int(sm.group(2)), int(sm.group(3))))

    # body: from first "1)" item; drop headers/noise/spec lines/legend
    body: list[tuple[int, str]] = []
    started = False
    skip_next_section = False
    for pno, ln in raw_lines:
        if not started:
            if _ITEM_START.match(ln) and ln.startswith("1)"):
                started = True
            else:
                continue
        if re.match(r"^revised bloom", ln, re.IGNORECASE):
            break
        if _SPEC_NEW.match(ln) or _SECTION.match(ln) or _NOISE.match(ln):
            continue
        body.append((pno, ln))

    # split body into numbered items, requiring sequential numbering
    items: list[tuple[int, int, list[str]]] = []   # (number, page, lines)
    expected = 1
    pending_number_only: tuple[int, int] | None = None
    for pno, ln in body:
        m = _ITEM_START.match(ln)
        if m and int(m.group(1)) == expected:
            items.append((expected, pno, [m.group(2)] if m.group(2) else []))
            expected += 1
        else:
            if items:
                items[-1][2].append(ln)

    questions: list[ParsedQuestion] = []
    for number, pno, ilines in items:
        segments: list[list[str]] = [[]]
        marks_seq: list[tuple[float, list[str], list[str]]] = []
        saw_or = False
        for ln in ilines:
            t = _TERMINATOR.match(ln)
            if t:
                cos, rbt = _labels(t.group(2), t.group(3))
                marks_seq.append((float(t.group(1)), cos, rbt))
                segments.append([])
            elif _OR.match(ln):
                saw_or = True
                segments[-1].append("\x00OR")
            else:
                segments[-1].append(ln)
        trailing = segments[-1] if len(segments) > len(marks_seq) else []
        segments = [s for s in segments if any(x for x in s if x != "\x00OR")]
        if len(segments) == len(marks_seq) + 1 and trailing and len(segments) > 1:
            # text printed after the last terminator (tables / formula fragments) continues that question
            segments = segments[:-1]
            segments[-1] = segments[-1] + [x for x in trailing if x != "\x00OR"]
        if len(segments) != len(marks_seq):
            paper.warnings.append(f"Q{number}: {len(segments)} text segments vs {len(marks_seq)} terminators")
        n = min(len(segments), len(marks_seq))
        for idx in range(n):
            seg_lines = [x for x in segments[idx] if x != "\x00OR"]
            txt = " ".join(seg_lines)
            part_label = None
            if (pm := re.match(r"^\(?([a-z])\)\s+", txt)) and n > 1:
                part_label = pm.group(1)
                txt = txt[pm.end():]
            elif n > 1:
                part_label = chr(ord("a") + idx)
            kind = "single" if n == 1 else ("alt" if saw_or else "part")
            marks, cos, rbt = marks_seq[idx]
            questions.append(ParsedQuestion(number, part_label, kind, _clean(txt), marks, cos, rbt, None, pno))

    # section assignment from specs (marks*count=total, items in order)
    cursor = 1
    for label, m_per_q, count, total in specs:
        n_items = 0
        for q in questions:
            if cursor <= q.number < cursor + count:
                q.section = label
                n_items = max(n_items, 1)
        paper.sections.append(ParsedSection(label, float(m_per_q), count, count, float(total),
                                            "Answer ALL the questions"))
        cursor += count
    paper.questions = questions
    if not specs:
        paper.warnings.append("no section specs found")
    _verify(paper)


def _clean_page(txt: str) -> str:
    return txt.replace("\u200b", "").replace("\xa0", " ")


# ------------------------------------------------------------------------------------ table layout
def _parse_table(doc: pymupdf.Document, paper: ParsedPaper) -> None:
    all_lines: list[str] = []
    markers: list[tuple[int, float, str, str]] = []  # (page, y, section label, instruction/spec blob)
    for pno, page in enumerate(doc, start=1):
        for b in page.get_text("blocks"):
            txt = _clean_page(b[4]).strip()
            all_lines.extend(_clean(x) for x in txt.split("\n") if x.strip())
            for ln in txt.split("\n"):
                if m := _SECTION.match(_clean(ln)):
                    markers.append((pno, b[1], m.group(1).upper(), ""))
                    break
    _header(all_lines, paper)
    paper.outcomes = _outcomes(all_lines)

    # section spec blobs: text between "SECTION X" and the next section / table
    full = "\n".join(all_lines)
    sec_blobs: dict[str, str] = {}
    for m in re.finditer(r"SECTION\s+([A-Z])\s*\n(.*?)(?=\nQ\.? ?No|\nSECTION\s+[A-Z]|\Z)", full, re.DOTALL):
        sec_blobs.setdefault(m.group(1).upper(), m.group(2))

    rows_out: list[dict] = []
    for pno, page in enumerate(doc, start=1):
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows or not rows[0] or "Q" not in (rows[0][0] or "") and "Revised" not in (rows[0][0] or ""):
                header_present = False
            header_present = bool(rows and rows[0] and re.match(r"^Q\.?\s*No", (rows[0][0] or ""), re.IGNORECASE))
            if rows and rows[0] and "Revised" in (rows[0][0] or ""):
                continue
            ty = t.bbox[1]
            sec = None
            for mp, my, label, _ in markers:
                if (mp, my) <= (pno, ty):
                    sec = label
            for r in (rows[1:] if header_present else rows):
                if len(r) < 4:
                    continue
                num = _clean(r[0] or "")
                txt = _clean((r[1] or "").replace("\n", " "))
                co = _clean((r[2] or "").replace("\n", " "))
                rbt = _clean((r[3] or "").replace("\n", " "))
                rows_out.append({"num": num, "txt": txt, "co": co, "rbt": rbt, "page": pno, "sec": sec})

    questions: list[ParsedQuestion] = []
    cur: ParsedQuestion | None = None
    for r in rows_out:
        if re.fullmatch(r"\d{1,2}", r["num"]):
            cos = [f"CO{n}" for n in re.findall(r"\d", r["co"])]
            rbt = [f"L{n}" for n in re.findall(r"L\s*(\d)", r["rbt"])]
            cur = ParsedQuestion(int(r["num"]), None, "single", r["txt"], None, cos, rbt, r["sec"], r["page"])
            questions.append(cur)
        elif cur is not None:
            # continuation row (page-split question text, split CO/RBT cell, or "(OR)" alternative)
            if r["txt"]:
                cur.text = _clean(cur.text + " " + r["txt"])
            if r["co"] and re.search(r"\d", r["co"]) and not cur.course_outcomes:
                cur.course_outcomes = [f"CO{n}" for n in re.findall(r"\d", r["co"])]
            elif r["co"] and re.fullmatch(r"\d", r["co"].strip()) and not cur.course_outcomes:
                cur.course_outcomes = [f"CO{r['co'].strip()}"]
            if r["rbt"] and not cur.rbt:
                cur.rbt = [f"L{n}" for n in re.findall(r"L\s*(\d)", r["rbt"])]
    # a bare digit on a continuation row (CO split across pages: ['', '', '1', ''])
    # is handled above; "CO 1" cell text is normalised by the digit regex.

    # split "(OR)" / " OR " alternatives inside the question text
    final: list[ParsedQuestion] = []
    for q in questions:
        parts = re.split(r"\s*\(OR\)\s*|\s+OR\s+(?=[A-Z])", q.text)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) <= 1:
            final.append(q)
            continue
        for i, p in enumerate(parts):
            final.append(ParsedQuestion(q.number, chr(ord("a") + i), "alt", p, None, q.course_outcomes,
                                        q.rbt, q.section, q.page))
    # section structure + per-question marks derived from the printed spec and the item count
    by_sec: dict[str, set[int]] = {}
    for q in final:
        if q.section:
            by_sec.setdefault(q.section, set()).add(q.number)
    for label, nums in by_sec.items():
        blob = sec_blobs.get(label, "")
        spec = _SPEC_OLD.search(blob)
        total = float(spec.group(3)) if spec else None
        if m := re.search(r"any\s+(\w+)", blob, re.IGNORECASE):
            n_ans = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                     "eight": 8, "nine": 9, "ten": 10}.get(m.group(1).lower())
            if n_ans is None and m.group(1).isdigit():
                n_ans = int(m.group(1))
        else:
            n_ans = len(nums)
        per_q = (total / n_ans) if total and n_ans else None
        instr = _clean(blob.split("\n")[0]) if blob else None
        paper.sections.append(ParsedSection(label, per_q, n_ans, len(nums), total, instr))
        for q in final:
            if q.section == label:
                q.marks = per_q
    paper.questions = final
    _verify(paper)


# ------------------------------------------------------------------------------------ verification
def _verify(paper: ParsedPaper) -> None:
    qs = paper.questions
    if not qs:
        paper.warnings.append("no questions parsed")
        return
    numbers = sorted({q.number for q in qs})
    if numbers != list(range(1, numbers[-1] + 1)):
        paper.warnings.append(f"non-contiguous question numbers: {numbers}")
    for q in qs:
        if not q.course_outcomes:
            paper.warnings.append(f"Q{q.number}{q.part or ''}: missing CO")
        if not q.rbt:
            paper.warnings.append(f"Q{q.number}{q.part or ''}: missing RBT level")
        if q.marks is None:
            paper.warnings.append(f"Q{q.number}{q.part or ''}: missing marks")
        if len(q.text) < 8:
            paper.warnings.append(f"Q{q.number}{q.part or ''}: very short text {q.text!r}")
    # marks must add up to the printed maximum (choice questions: count one alternative)
    for s in paper.sections:
        sec_qs = [q for q in qs if q.section == s.label]
        if not sec_qs or s.total_marks is None:
            continue
        per_item: dict[int, float] = {}
        for q in sec_qs:
            if q.marks is None:
                continue
            if q.kind == "alt":
                per_item[q.number] = max(per_item.get(q.number, 0), q.marks)
            else:
                per_item[q.number] = per_item.get(q.number, 0) + q.marks
        got = sum(per_item.values())
        listed = len(per_item)
        if s.questions_to_answer and listed == s.questions_to_answer and abs(got - s.total_marks) > 1e-6:
            paper.warnings.append(f"Section {s.label}: marks sum {got} != printed total {s.total_marks}")
        if s.questions_to_answer and listed < s.questions_to_answer:
            paper.warnings.append(f"Section {s.label}: parsed {listed} items, paper asks for {s.questions_to_answer}")
    if paper.max_marks:
        total = sum(s.total_marks or 0 for s in paper.sections)
        if abs(total - paper.max_marks) > 1e-6:
            paper.warnings.append(f"section totals {total} != Max Marks {paper.max_marks}")


# ---------------------------------------------------------------------------------------- public
def parse_paper(path: str | Path) -> ParsedPaper:
    path = Path(path)
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # corrupt / not a PDF / unreadable
        raise PaperParseError(f"{path.name}: cannot open as a PDF ({exc})") from exc
    if doc.needs_pass:
        raise PaperParseError(f"{path.name}: PDF is password-protected")
    if len(doc) == 0:
        raise PaperParseError(f"{path.name}: PDF has no pages")
    sample = "\n".join(_clean_page(p.get_text()) for p in doc)
    sample = re.sub(r"(\(\s*CO\s*\d[^)\n]*,)\s*\n\s*(L\s*\d[^)\n]*\))", r"\1 \2", sample)
    sample = re.sub(r"(?m)^(\d+(?:\.\d+)?)[ \t]*\n[ \t]*(\(\s*CO\s*\d)", r"\1 \2", sample)
    layout = "terminator" if re.search(r"^\d+\s*\(\s*CO\s*\d", sample, re.MULTILINE | re.IGNORECASE) else "table"
    paper = ParsedPaper(file=path.name, layout=layout)
    (_parse_terminator if layout == "terminator" else _parse_table)(doc, paper)
    return paper
