import sys; sys.path.insert(0,".")
import json
from src.generation.blueprint import default_blueprint
from src.generation.render import PaperQuestion, render_pdf, render_docx
from src.extraction.christ_parser import parse_paper
import pymupdf
bp = default_blueprint("BCA202-3", "November 2025")
print(bp.validate(), [ (s.label,s.n_items,s.marks_each,s.n_choice) for s in bp.sections])
qs=[]; n=0
for s in bp.sections:
    from src.optimization.allocator import _choice_positions
    ch=_choice_positions(s.n_items,s.n_choice)
    for i in range(s.n_items):
        n+=1
        co=sorted(bp.outcomes)[n%len(bp.outcomes)]
        qs.append(PaperQuestion(s.label,n,"a" if i in ch else None,f"Explain test concept {n} of the operating system in a short answer with a suitable example for the learners.",s.marks_each,co,2+(n%3)))
        if i in ch: qs.append(PaperQuestion(s.label,n,"b",f"Describe alternative concept {n} with a neat diagram and one worked example.",s.marks_each,co,2+(n%3)))
p=render_pdf(bp,qs,"scratch/smoke.pdf"); render_docx(bp,qs,"scratch/smoke.docx")
pp=parse_paper(p)
print(pp.layout, pp.course_code, pp.max_marks, pp.duration_minutes, pp.semester, pp.exam_session, "n_q",len(pp.questions),"warn",pp.warnings)
print([(s.label,s.marks_per_question,s.questions_to_answer,s.total_marks) for s in pp.sections])
d=pymupdf.open(p); print("pages",len(d)); d[0].get_pixmap(dpi=80).save("scratch/img/smoke_p1.png")
