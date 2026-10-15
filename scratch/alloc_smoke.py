import sys, time; sys.path.insert(0,".")
from src.generation.blueprint import default_blueprint, load_papers, load_questions
from src.generation.topics import build_history
from src.optimization.allocator import allocate, InfeasibleBlueprint
papers, questions = load_papers(), load_questions()
code="BCA201-3"
bp = default_blueprint(code, "November 2025", papers=papers, questions=questions)
base=code.split("-")[0]
cq=[q for q in questions if (q["course_code"] or "").split("-")[0]==base]
order=[p["paper_id"] for p in papers if (p["course_code"] or "").split("-")[0]==base]
t=time.time()
prof=build_history(cq, base, order, questions)
print("clusters:", [(c.id,c.label,c.freq) for c in prof.clusters], f"{time.time()-t:.1f}s")
t=time.time(); a=allocate(bp, prof); print("solve", f"{time.time()-t:.1f}s")
for s in a.slots[:12]: print(s.section, s.item, s.part, s.marks, s.co, f"L{s.level}", prof.clusters[s.cluster].label)
import json; print(json.dumps(a.report, indent=1)[:900])
bp.bloom_target={2:0.3,3:0.4,4:0.3}
a=allocate(bp, prof); print("explicit target ->", a.report["bloom_marks_share"], a.report["bloom_within_tolerance"], a.report["bloom_deviation_marks"])
bp.bloom_target={1:0.1,2:0.1,3:0.1,4:0.1,5:0.1,6:0.5}
try: allocate(bp,prof)
except InfeasibleBlueprint as e: print("infeasible ->", e.problems)
bp.bloom_target={1:.001,2:.5,3:.499}
try: allocate(bp,prof)
except InfeasibleBlueprint as e: print("infeasible ->", e.problems)
