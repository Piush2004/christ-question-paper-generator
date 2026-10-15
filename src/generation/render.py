"""Single paper template, two renderers (PDF + DOCX). Every generated paper goes through this module,
so every paper has the identical CHRIST end-semester layout:

    right-aligned "Syllabus Year"
    centred: CHRIST (Deemed to be University), Bengaluru - 560029 / <exam title - session> / <programme SEMESTER - X>
    Course Code | Max Marks  /  Course Name | Duration
    General Instructions (bullets) — fixed institutional text
    Course Outcome: Students will be able to: CO1 ...
    per section: centred bold "Section X" with the "marks*items=total" spec at the right,
                 rows  [N)] [question text] [marks] [(COk, Lj)],  centred bold "OR" between alternatives
    footer legend: Revised Bloom's Taxonomy (RBT) Levels

`tests/test_generation_format.py` re-parses every rendered PDF with the same parser used on the real
papers and checks it reproduces the blueprint, which is how "same format for all papers" is enforced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from fpdf import FPDF

from src.generation.blueprint import RBT_LEGEND, STANDARD_INSTRUCTIONS, Blueprint


@dataclass
class PaperQuestion:
    section: str
    item: int
    part: str | None          # None | "a" | "b"
    text: str
    marks: float
    co: str
    level: int


def _fonts() -> dict[str, str]:
    win = Path("C:/Windows/Fonts")
    if (win / "times.ttf").exists():
        return {"": str(win / "times.ttf"), "B": str(win / "timesbd.ttf"), "I": str(win / "timesi.ttf")}
    import matplotlib
    d = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
    return {"": str(d / "DejaVuSerif.ttf"), "B": str(d / "DejaVuSerif-Bold.ttf"), "I": str(d / "DejaVuSerif-Italic.ttf")}


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _group(questions: list[PaperQuestion]) -> dict[str, dict[int, list[PaperQuestion]]]:
    out: dict[str, dict[int, list[PaperQuestion]]] = {}
    for q in questions:
        out.setdefault(q.section, {}).setdefault(q.item, []).append(q)
    return out


def _marks(m: float) -> str:
    return f"{m:g}"


# ------------------------------------------------------------------------------------------- PDF
class _Pdf(FPDF):
    draft_footer: str = ""

    def footer(self) -> None:
        if self.draft_footer:
            self.set_y(-12)
            self.set_font("PaperSerif", "I", 8)
            self.set_text_color(110, 110, 110)
            self.cell(0, 5, self.draft_footer, align="C")
            self.set_text_color(0, 0, 0)


def render_pdf(bp: Blueprint, questions: list[PaperQuestion], path: str | Path, *, draft: bool = True) -> Path:
    f = _fonts()
    pdf = _Pdf(format="A4", unit="mm")
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_font("PaperSerif", "", f[""]); pdf.add_font("PaperSerif", "B", f["B"]); pdf.add_font("PaperSerif", "I", f["I"])
    if draft:
        pdf.draft_footer = "AI-assisted draft - teacher review and approval required before use"
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin

    def line(text, style="", size=11, align="L", h=6.0):
        pdf.set_font("PaperSerif", style, size)
        pdf.cell(W, h, text, align=align, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("PaperSerif", "B", 10)
    pdf.cell(W, 5, f"Syllabus Year: {bp.syllabus_year}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    line("CHRIST (Deemed to be University), Bengaluru - 560029", "B", 11, "C")
    line(bp.header_title, "B", 11, "C")
    line(f"{bp.program} SEMESTER - {bp.semester_roman}", "B", 11, "C")
    pdf.ln(1)
    for left, right in [(f"Course Code: {bp.course_code}", f"Max Marks: {bp.max_marks}"),
                        (f"Course Name: {bp.course_name}", f"Duration: {_hhmm(bp.duration_minutes)}")]:
        y = pdf.get_y()
        pdf.set_font("PaperSerif", "B", 11)
        pdf.cell(W * 0.7, 6, left)
        pdf.set_xy(pdf.l_margin + W * 0.7, y)
        pdf.cell(W * 0.3, 6, right, align="R", new_x="LMARGIN", new_y="NEXT")
    line("General Instructions:", "B", 11)
    pdf.set_font("PaperSerif", "", 10)
    for ins in STANDARD_INSTRUCTIONS:
        pdf.set_x(pdf.l_margin + 4)
        pdf.cell(4, 4.6, "\u2022")
        pdf.multi_cell(W - 8, 4.6, ins, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_draw_color(190, 190, 190)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("PaperSerif", "B", 11)
    pdf.cell(pdf.get_string_width("Course Outcome: ") + 1, 5.5, "Course Outcome:")
    pdf.set_font("PaperSerif", "", 11)
    pdf.cell(0, 5.5, " Students will be able to:", new_x="LMARGIN", new_y="NEXT")
    for k in sorted(bp.outcomes):
        pdf.multi_cell(W, 5.2, f"{k}: {bp.outcomes[k]}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    grouped = _group(questions)
    NUM_W, MARK_W, CO_W = 17.0, 10.0, 22.0
    TXT_W = W - NUM_W - MARK_W - CO_W - 2
    for sec in bp.sections:
        if pdf.get_y() > pdf.h - 45:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_font("PaperSerif", "B", 11)
        pdf.set_xy(pdf.l_margin + W * 0.80, y)
        pdf.cell(W * 0.20, 6, sec.spec_line, align="R")            # spec first => extracted before the label
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(W, 6, f"Section {sec.label}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        for item_no in sorted(grouped.get(sec.label, {})):
            parts = grouped[sec.label][item_no]
            for pi, q in enumerate(parts):
                if pi > 0:
                    pdf.set_font("PaperSerif", "B", 11)
                    pdf.cell(W, 6, "OR", align="C", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("PaperSerif", "", 11)
                n_lines = len(pdf.multi_cell(TXT_W, 5.3, q.text, dry_run=True, output="LINES"))
                need = max(n_lines, 1) * 5.3 + 2
                if pdf.get_y() + need > pdf.h - 16:
                    pdf.add_page()
                y0 = pdf.get_y()
                label = f"{item_no})" + (f" {q.part})" if (q.part == "a") else "") if q.part != "b" else f"{q.part})"
                pdf.set_xy(pdf.l_margin, y0)
                pdf.set_font("PaperSerif", "B", 11)
                pdf.cell(NUM_W, 5.3, label, align="R")
                pdf.set_xy(pdf.l_margin + NUM_W + 2, y0)
                pdf.set_font("PaperSerif", "", 11)
                pdf.multi_cell(TXT_W, 5.3, q.text, new_x="LEFT", new_y="NEXT")
                y_end = pdf.get_y()
                pdf.set_xy(pdf.l_margin + NUM_W + 2 + TXT_W, y0)
                pdf.set_font("PaperSerif", "B", 11)
                pdf.cell(MARK_W, 5.3, _marks(q.marks), align="R")
                pdf.set_font("PaperSerif", "", 11)
                pdf.cell(CO_W, 5.3, f"(CO{q.co[2:]}, L{q.level})", align="R")
                pdf.set_xy(pdf.l_margin, max(y_end, y0 + 5.3) + 1.6)
        pdf.ln(2)

    pdf.ln(2)
    pdf.set_font("PaperSerif", "B", 10)
    pdf.cell(W, 5, "Revised Bloom's Taxonomy (RBT) Levels", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("PaperSerif", "", 10)
    for lg in RBT_LEGEND:
        pdf.cell(W, 4.6, lg, new_x="LMARGIN", new_y="NEXT")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return path


# ------------------------------------------------------------------------------------------ DOCX
def render_docx(bp: Blueprint, questions: list[PaperQuestion], path: str | Path, *, draft: bool = True) -> Path:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt

    doc = Document()
    sec0 = doc.sections[0]
    sec0.page_width, sec0.page_height = Mm(210), Mm(297)
    sec0.left_margin = sec0.right_margin = Mm(14)
    sec0.top_margin, sec0.bottom_margin = Mm(12), Mm(14)
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    def para(text="", bold=False, align=None, size=None, italic=False, space_after=2):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if align:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(0)
        return p

    para(f"Syllabus Year: {bp.syllabus_year}", True, WD_ALIGN_PARAGRAPH.RIGHT, 10)
    C = WD_ALIGN_PARAGRAPH.CENTER
    para("CHRIST (Deemed to be University), Bengaluru - 560029", True, C)
    para(bp.header_title, True, C)
    para(f"{bp.program} SEMESTER - {bp.semester_roman}", True, C)
    hdr = doc.add_table(rows=2, cols=2)
    for r, (a, b) in enumerate([(f"Course Code: {bp.course_code}", f"Max Marks: {bp.max_marks}"),
                                (f"Course Name: {bp.course_name}", f"Duration: {_hhmm(bp.duration_minutes)}")]):
        hdr.cell(r, 0).text, hdr.cell(r, 1).text = a, b
        for c in (0, 1):
            for run in hdr.cell(r, c).paragraphs[0].runs:
                run.bold = True
        hdr.cell(r, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    para("General Instructions:", True)
    for ins in STANDARD_INSTRUCTIONS:
        p = doc.add_paragraph(ins, style="List Bullet")
        p.paragraph_format.space_after = Pt(0)
        for run in p.runs:
            run.font.size = Pt(10)
    p = doc.add_paragraph()
    p.add_run("Course Outcome:").bold = True
    p.add_run(" Students will be able to:")
    for k in sorted(bp.outcomes):
        para(f"{k}: {bp.outcomes[k]}", space_after=0)

    grouped = _group(questions)
    for sec in bp.sections:
        doc.add_paragraph()
        t = doc.add_table(rows=1, cols=3)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.cell(0, 1).text = f"Section {sec.label}"
        t.cell(0, 2).text = sec.spec_line
        t.cell(0, 1).paragraphs[0].alignment = C
        t.cell(0, 2).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for c in (1, 2):
            for run in t.cell(0, c).paragraphs[0].runs:
                run.bold = True
        tbl = doc.add_table(rows=0, cols=4)
        widths = [Mm(17), Mm(125), Mm(10), Mm(30)]
        for item_no in sorted(grouped.get(sec.label, {})):
            for pi, q in enumerate(grouped[sec.label][item_no]):
                if pi > 0:
                    row = tbl.add_row()
                    m = row.cells[0].merge(row.cells[3])
                    m.text = "OR"
                    m.paragraphs[0].alignment = C
                    for run in m.paragraphs[0].runs:
                        run.bold = True
                row = tbl.add_row()
                label = f"{item_no})" + (" a)" if q.part == "a" else "") if q.part != "b" else "b)"
                row.cells[0].text = label
                row.cells[1].text = q.text
                row.cells[2].text = _marks(q.marks)
                row.cells[3].text = f"(CO{q.co[2:]}, L{q.level})"
                row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                row.cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for run in row.cells[0].paragraphs[0].runs + row.cells[2].paragraphs[0].runs:
                    run.bold = True
                for c, w in zip(row.cells, widths):
                    c.width = w
    doc.add_paragraph()
    para("Revised Bloom's Taxonomy (RBT) Levels", True, size=10)
    for lg in RBT_LEGEND:
        para(lg, size=10, space_after=0)
    if draft:
        footer = sec0.footer.paragraphs[0]
        footer.text = "AI-assisted draft - teacher review and approval required before use"
        footer.alignment = C
        for run in footer.runs:
            run.italic, run.font.size = True, Pt(8)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
