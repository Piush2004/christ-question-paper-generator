import glob, os, sys, hashlib
sys.path.insert(0, ".")
from src.extraction.christ_parser import parse_paper
seen = {}
for f in sorted(glob.glob("data/raw/databank/*.pdf")):
    h = hashlib.sha256(open(f,"rb").read()).hexdigest()[:10]
    dup = seen.get(h)
    seen.setdefault(h, os.path.basename(f))
    try:
        p = parse_paper(f)
        nq = len(p.questions)
        miss_l = sum(1 for q in p.questions if not q.rbt)
        miss_co = sum(1 for q in p.questions if not q.course_outcomes)
        print(f"{os.path.basename(f):22s} {p.layout:10s} {p.course_code} {str(p.course_name)[:28]:28s} {p.exam_session} nq={nq:3d} noRBT={miss_l:3d} noCO={miss_co:3d} warn={len(p.warnings):3d} dup={dup}")
    except Exception as e:
        print(f"{os.path.basename(f):22s} ERROR {type(e).__name__}: {str(e)[:80]}")
