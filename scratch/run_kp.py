import glob, os, sys, hashlib, csv
sys.path.insert(0, ".")
from src.extraction.christ_parser import parse_paper
meta = {r["original_filename"]: r for r in csv.DictReader(open("data/raw/knowledgepro/manifests/knowledgepro_manifest.csv", encoding="utf-8"))}
for f in sorted(glob.glob("data/raw/knowledgepro/documents/*.dat")):
    b = os.path.basename(f); m = meta.get(b, {})
    try:
        p = parse_paper(f)
        miss_l = sum(1 for q in p.questions if not q.rbt)
        print(f"{b:10s} {m.get('course_code','?'):8s} {m.get('course_name','?')[:30]:30s} {m.get('exam_type','?')[-24:]:24s} {p.layout:10s} nq={len(p.questions):3d} noRBT={miss_l:3d} warn={len(p.warnings)}")
    except Exception as e:
        print(f"{b:10s} ERROR {type(e).__name__}: {str(e)[:80]}")
