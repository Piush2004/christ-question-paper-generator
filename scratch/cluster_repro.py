import sys, json, warnings; sys.path.insert(0, "."); warnings.filterwarnings("ignore")
import numpy as np
from src.generation.blueprint import load_papers, load_questions
from src.generation.pipeline import history_for
from src.embeddings.encoder import encode
papers, questions = load_papers(), load_questions()
p = history_for("graph_theory", papers, questions, exclude_paper_ids={"BCA201-4_April2025"})
sig = [(c.id, c.freq, sorted(c.member_ids)[:3]) for c in p.clusters]
txt = [q["text"] for q in p.all_questions][:50]
e = encode(txt)
print(json.dumps({"clusters": sig, "emb_checksum": float(np.round(e.sum(), 6)), "emb_first": [float(x) for x in e[0][:4]]}))
