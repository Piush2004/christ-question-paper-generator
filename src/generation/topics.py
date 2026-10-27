"""Historical topic structure for one course, learned from its past questions (no syllabus needed).

Topics are *unsupervised* clusters of question embeddings (KMeans, deterministic seed), labelled with
their most characteristic TF-IDF terms. They are an approximation of syllabus topics — good enough to
(a) spread a new paper across the material the course has actually examined and (b) measure topic
coverage/repetition — and are reported as "historical topic clusters", never as official syllabus units.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from src.embeddings.encoder import encode
from src.extraction.syllabus_parser import SyllabusCourse


@dataclass
class TopicCluster:
    id: int
    label: str
    keywords: list[str]
    member_ids: list[str]
    centroid: np.ndarray
    freq: int
    co_counts: dict[str, int] = field(default_factory=dict)
    last_paper_id: str | None = None


@dataclass
class HistoryProfile:
    course_base: str
    questions: list[dict]
    embeddings: np.ndarray
    clusters: list[TopicCluster]
    co_share: dict[str, float]                 # share of historical marks per CO
    bloom_prior_by_marks: dict[float, np.ndarray]  # marks -> P(level L1..L6)
    recent_cluster_ids: set[int]               # clusters present in the most recent paper
    paper_ids: list[str]
    # ALL historical questions regardless of source-quality status: copy/novelty detection must see everything
    all_questions: list[dict] = field(default_factory=list)
    all_embeddings: np.ndarray | None = None
    excluded_from_exemplars: dict[str, str] = field(default_factory=dict)   # question_id -> status
    topics_source: str = "unsupervised_cluster"

    def cluster_of(self, emb: np.ndarray) -> int:
        sims = [float(emb @ c.centroid) for c in self.clusters]
        return int(np.argmax(sims))


def _norm_marks(m: float) -> float:
    return float(m)


def _cluster_co_counts_and_last(idx, qs: list[dict], paper_order: list[str]) -> tuple[dict[str, int], str | None]:
    co_counts: dict[str, int] = {}
    last = None
    for i in idx:
        for co in qs[i]["course_outcomes"]:
            co_counts[co] = co_counts.get(co, 0) + 1
        pid = qs[i]["paper_id"]
        if pid in paper_order and (last is None or paper_order.index(pid) > paper_order.index(last)):
            last = pid
    return co_counts, last


def build_history(questions: list[dict], course_base: str, paper_order: list[str], all_questions_for_prior: list[dict],
                  k: int | None = None, seed: int = 7, source_status: dict[str, str] | None = None,
                  syllabus: SyllabusCourse | None = None) -> HistoryProfile:
    """`questions`: this course's historical questions (already restricted to the allowed time window).
    `paper_order`: paper ids oldest->newest. `all_questions_for_prior`: pool used for the marks-conditional
    Bloom prior (other courses allowed — it only encodes how marks relate to cognitive level)."""
    # Exemplars / topic clusters use only questions whose extracted text is usable; copy detection (all_*) uses every question.
    status = source_status or {}
    all_q = [q for q in questions if q["n_words"] >= 2]
    all_emb = encode([q["text"] for q in all_q])
    keep = [i for i, q in enumerate(all_q) if q["n_words"] >= 4 and status.get(q["question_id"], "VALID") in ("VALID", "NEEDS_HUMAN_REVIEW")]
    excluded = {q["question_id"]: status.get(q["question_id"], "short") for i, q in enumerate(all_q) if i not in set(keep)}
    qs = [all_q[i] for i in keep]
    texts = [q["text"] for q in qs]
    emb = all_emb[keep]
    n = len(qs)

    topics_source = "unsupervised_cluster"
    clusters: list[TopicCluster] = []
    if syllabus is not None and syllabus.units:
        topics_source = "syllabus"
        centroids = encode([f"{u.title}. {u.topics}" for u in syllabus.units])
        assignment = np.argmax(emb @ centroids.T, axis=1) if n else np.array([], dtype=int)
        for uidx, unit in enumerate(syllabus.units):
            idx = np.where(assignment == uidx)[0]
            co_counts, last = _cluster_co_counts_and_last(idx, qs, paper_order)
            clusters.append(TopicCluster(uidx, unit.title, unit.topics.split()[:6],
                                         [qs[i]["question_id"] for i in idx], centroids[uidx],
                                         len(idx), co_counts, last))
    else:
        k = k or int(min(8, max(3, round(n / 7))))
        k = min(k, n)
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(emb)
        tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_features=4000, sublinear_tf=True)
        X = tfidf.fit_transform(texts)
        terms = np.array(tfidf.get_feature_names_out())
        for cid in range(k):
            idx = np.where(km.labels_ == cid)[0]
            centroid = emb[idx].mean(axis=0)
            centroid /= (np.linalg.norm(centroid) + 1e-9)
            scores = np.asarray(X[idx].mean(axis=0)).ravel()
            kw = [t for t in terms[np.argsort(-scores)[:6]]]
            co_counts, last = _cluster_co_counts_and_last(idx, qs, paper_order)
            clusters.append(TopicCluster(cid, ", ".join(kw[:3]), kw, [qs[i]["question_id"] for i in idx], centroid,
                                         len(idx), co_counts, last))
    marks_by_co: dict[str, float] = {}
    for q in qs:
        for co in q["course_outcomes"][:1]:
            marks_by_co[co] = marks_by_co.get(co, 0.0) + float(q["marks"])
    tot = sum(marks_by_co.values()) or 1.0
    co_share = {co: v / tot for co, v in marks_by_co.items()}

    prior: dict[float, np.ndarray] = {}
    pool = [q for q in all_questions_for_prior if q["rbt"]]
    for m in sorted({float(q["marks"]) for q in pool}):
        counts = np.ones(6) * 0.5  # Laplace-style smoothing
        for q in pool:
            if abs(float(q["marks"]) - m) < 1e-9:
                counts[int(q["rbt"][0][1]) - 1] += 1
        prior[m] = counts / counts.sum()
    newest = paper_order[-1] if paper_order else None
    recent = {c.id for c in clusters if c.last_paper_id == newest}
    return HistoryProfile(course_base, qs, emb, clusters, co_share, prior, recent, paper_order, all_q, all_emb, excluded,
                          topics_source)


def marks_prior(profile: HistoryProfile, marks: float) -> np.ndarray:
    keys = sorted(profile.bloom_prior_by_marks)
    nearest = min(keys, key=lambda k: abs(k - marks))
    return profile.bloom_prior_by_marks[nearest]
