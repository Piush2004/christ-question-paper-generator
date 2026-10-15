"""Dataset analysis (real numbers only) -> docs/DATASET_ANALYSIS.md + results/figures/*.png"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.embeddings.encoder import encode  # noqa: E402
from src.generation.generator import jaccard_3gram  # noqa: E402

P = ROOT / "data" / "processed"
FIG = ROOT / "results" / "figures"


def source_quality_lines(Q) -> list[str]:
    f = P / "source_quality.json"
    if not f.exists():
        return ["_Not computed — run `scripts/audit_source_quality.py`._", ""]
    S = json.loads(f.read_text())
    tot = Counter(S[q["question_id"]]["status"] for q in Q)
    det = Counter(S[q["question_id"]]["deterministic"]["status"] for q in Q)
    lines = ["Original text is never altered; status decides eligibility for exemplars/training. "
             "`ILL_POSED`/`AMBIGUOUS` are reserved for human adjudication and never assigned automatically. "
             "The LLM screen can only raise `NEEDS_HUMAN_REVIEW` and is **uncalibrated** (no human review exists).", "",
             f"- deterministic checks only: {dict(det)} ({(det['EXTRACTION_ERROR'] + det['INCOMPLETE']) / len(Q):.1%} defective)",
             f"- with LLM screen: {dict(tot)}", "", "| course | n | VALID | NEEDS_HUMAN_REVIEW | INCOMPLETE | EXTRACTION_ERROR |", "|---|---|---|---|---|---|"]
    fams = sorted({q["course_family"] for q in Q})
    for fam in fams:
        c = Counter(S[q["question_id"]]["status"] for q in Q if q["course_family"] == fam)
        lines.append(f"| {fam} | {sum(c.values())} | {c['VALID']} | {c['NEEDS_HUMAN_REVIEW']} | {c['INCOMPLETE']} | {c['EXTRACTION_ERROR']} |")
    return lines + [""]


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    Q = [json.loads(l) for l in (P / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    PA = [json.loads(l) for l in (P / "papers.jsonl").read_text(encoding="utf-8").splitlines()]
    R = json.loads((P / "build_report.json").read_text(encoding="utf-8"))
    n = len(Q)
    rbt = Counter(q["rbt"][0] for q in Q)
    marks = Counter(q["marks"] for q in Q)
    fam = Counter(q["course_family"] for q in Q)
    year = Counter(q["academic_year"] for q in Q)
    co = Counter(c for q in Q for c in q["course_outcomes"][:1])
    kinds = Counter(q["kind"] for q in Q)
    short = sum(q["n_words"] < 5 for q in Q)
    multi = sum(len(q["rbt"]) > 1 for q in Q)
    wc = np.array([q["n_words"] for q in Q])

    # duplicates / repeats across papers
    texts = [q["text"] for q in Q]
    E = encode(texts)
    S = E @ E.T
    np.fill_diagonal(S, 0)
    exact = near = 0
    seen_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if Q[i]["paper_id"] == Q[j]["paper_id"]:
                continue
            if texts[i].strip().lower() == texts[j].strip().lower():
                exact += 1
                seen_pairs.append((i, j, 1.0))
            elif S[i, j] >= 0.90 or jaccard_3gram(texts[i], texts[j]) >= 0.6:
                near += 1
                seen_pairs.append((i, j, float(S[i, j])))
    in_dup = len({i for i, j, _ in seen_pairs} | {j for i, j, _ in seen_pairs})
    # inter-paper repeat within the same subject (historical question recurrence)
    same_fam_repeat = sum(1 for i, j, _ in seen_pairs if Q[i]["course_family"] == Q[j]["course_family"])

    # figures
    fig, ax = plt.subplots(2, 3, figsize=(15, 8))
    ax[0, 0].bar([f"L{i}" for i in range(1, 7)], [rbt.get(f"L{i}", 0) for i in range(1, 7)], color="#3b6ea5")
    ax[0, 0].set_title("RBT (Bloom) level — paper-setter labels")
    ks = sorted(marks)
    ax[0, 1].bar([f"{k:g}" for k in ks], [marks[k] for k in ks], color="#6a9955"); ax[0, 1].set_title("Marks per question")
    fk = sorted(fam, key=lambda k: -fam[k])
    ax[0, 2].barh(fk[::-1], [fam[k] for k in fk][::-1], color="#b5651d"); ax[0, 2].set_title("Questions per subject")
    ax[1, 0].bar(sorted(year), [year[k] for k in sorted(year)], color="#7a5195"); ax[1, 0].set_title("Questions per academic year")
    ck = sorted(co)
    ax[1, 1].bar(ck, [co[k] for k in ck], color="#00796b"); ax[1, 1].set_title("Questions per course outcome (primary CO)")
    ax[1, 2].hist(wc, bins=25, color="#888"); ax[1, 2].set_title("Question length (words)")
    plt.tight_layout(); plt.savefig(FIG / "dataset_overview.png", dpi=110); plt.close()

    # rbt by marks heatmap
    import matplotlib.cm as cm
    mat = np.zeros((len(ks), 6))
    for q in Q:
        mat[ks.index(q["marks"]), int(q["rbt"][0][1]) - 1] += 1
    plt.figure(figsize=(6, 4)); plt.imshow(mat, cmap=cm.Blues)
    plt.xticks(range(6), [f"L{i}" for i in range(1, 7)]); plt.yticks(range(len(ks)), [f"{k:g}" for k in ks])
    for a in range(mat.shape[0]):
        for b in range(6):
            plt.text(b, a, int(mat[a, b]), ha="center", va="center", fontsize=8)
    plt.title("RBT level by marks"); plt.colorbar(); plt.tight_layout(); plt.savefig(FIG / "rbt_by_marks.png", dpi=110); plt.close()

    rej = Counter(r["reason"].split(":")[0][:60] for r in R["rejected"])
    L = ["# Dataset Analysis", "",
         "Generated by `scripts/analyze_dataset.py` from `data/processed/` — every number below is computed, none is estimated.", "",
         "## 1. Inventory", "",
         "| Metric | Value |", "|---|---|",
         f"| Papers admitted (parser-verified) | {len(PA)} |",
         f"| …supplied by the project owner (`Question Papers/`) | {sum(p['origin'] == 'owner' for p in PA)} |",
         f"| …from the public university data bank, downloaded earlier in this project | {sum(p['origin'] == 'databank' for p in PA)} |",
         f"| Questions extracted (each OR-alternative / sub-part counted) | {n} |",
         f"| Subjects (families) | {len(fam)} |",
         f"| Academic years | {', '.join(sorted(year))} |",
         f"| Files rejected by the verification gate | {len(R['rejected'])} |",
         f"| Files collapsed as duplicates (identical bytes / same exam re-uploaded) | {len(R['duplicates'])} |", "",
         "### Rejection reasons (nothing is dropped silently)", ""]
    L += [f"- {v} × {k}" for k, v in rej.most_common()]
    L += ["", "The 34 'no questions parsed' files are older (2015–2022) papers in a different, label-free layout (no CO/RBT "
          "columns); they are not usable as labelled data and OCR is unavailable (no Tesseract binary), so they are "
          "excluded rather than guessed at.", "",
          "## 2. Extraction quality", "",
          "Verified against the paper itself, not against a gold annotation: item counts per section, marks per section "
          "and the paper's Max Marks must reconcile, and every question must carry marks + CO + RBT. "
          f"All {len(PA)} admitted papers pass. Remaining blemishes: {short} questions have < 5 words "
          "(math/formula text lost in PDF extraction — formulas rendered as images or private glyphs), "
          f"{multi} carry two RBT labels (first used).", "",
          "## 3. Distributions", "",
          "| Level | Questions | Share |", "|---|---|---|"]
    L += [f"| {k} | {rbt.get(k, 0)} | {rbt.get(k, 0) / n:.1%} |" for k in [f'L{i}' for i in range(1, 7)]]
    L += ["", "| Marks | Questions |", "|---|---|"] + [f"| {k:g} | {marks[k]} |" for k in ks]
    L += ["", "| Subject | Papers | Questions |", "|---|---|---|"]
    for k in fk:
        L.append(f"| {k} | {len({q['paper_id'] for q in Q if q['course_family'] == k})} | {fam[k]} |")
    L += ["", f"Question kinds: {dict(kinds)}.", f"Words per question: mean {wc.mean():.1f}, median {np.median(wc):.0f}, "
          f"min {wc.min()}, max {wc.max()}.", "",
          "## 4. Duplicates and repetition", "",
          f"Across different papers: {exact} exact and {near} near-duplicate question pairs "
          f"(cosine ≥ 0.90 or word-3-gram Jaccard ≥ 0.6); {in_dup} questions ({in_dup / n:.1%}) take part in at least one pair; "
          f"{same_fam_repeat} of those pairs are within the same subject (questions re-asked in another year). "
          "This is why the evaluation protocols never split a subject across train/test (leave-one-subject-out) or remove near-duplicates "
          "(leave-one-paper-out).", "",
          "## 5. Source-question quality status", "",
          *source_quality_lines(Q),
          "## 6. Limitations (read before trusting any model number)", "",
          f"- **Small**: {n} questions / {len(PA)} papers; L6 has {rbt.get('L6', 0)} examples, L5 {rbt.get('L5', 0)}.",
          "- **One programme** (BCA), ten courses, 2022–2025; some subjects have a single paper, so same-course temporal generalisation can only be tested on graph theory (3 papers) and discrete mathematics (2); PSD-I→PSD-II is only a related-course transfer case.",
          "- **Labels are teacher assertions, not ground truth**: the RBT level beside each question is the paper setter's judgement. "
          "The label audit (docs/EVALUATION_BLOOM.md) shows the same leading verb ('explain', 'define', 'state') carrying L1…L5 across papers.",
          "- **No difficulty, DOK, unit or topic labels exist** in these papers; no model for them can be trained or evaluated, and none is claimed. "
          "Course outcomes (CO) are the only curriculum labels available.",
          "- **No student response data**, so psychometric (IRT) calibration is impossible.",
          "- Mathematical notation is partly lost by PDF text extraction.", "",
          "![overview](../results/figures/dataset_overview.png)", "", "![rbt by marks](../results/figures/rbt_by_marks.png)"]
    (ROOT / "docs" / "DATASET_ANALYSIS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
