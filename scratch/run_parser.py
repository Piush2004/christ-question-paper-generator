import glob, os, sys
sys.path.insert(0, ".")
from src.extraction.christ_parser import parse_paper
for f in sorted(glob.glob("Question Papers/*.pdf")):
    p = parse_paper(f)
    print("="*90)
    print(p.file, "|", p.layout, "|", p.course_code, p.course_name, "| sem", p.semester, "|", p.exam_session, p.academic_year, "| max", p.max_marks, "| dur", p.duration_minutes, "| prog", p.program)
    print("  COs:", {k: v[:40] for k, v in p.outcomes.items()})
    print("  sections:", [(s.label, s.marks_per_question, s.questions_to_answer, s.items_listed, s.total_marks) for s in p.sections])
    print("  n questions:", len(p.questions), "| warnings:", len(p.warnings))
    for w in p.warnings[:12]: print("   WARN", w)
    if "-v" in sys.argv:
        for q in p.questions:
            print(f"   [{q.section}] {q.number}{q.part or ''} {q.kind} m={q.marks} {q.course_outcomes} {q.rbt} :: {q.text[:70]!r}")
