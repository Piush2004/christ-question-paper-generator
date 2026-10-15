from pathlib import Path

p = Path(r"D:\Projects\Christ Question Paper model\src\generation\generator.py")
s = p.read_text(encoding="utf-8")
start = s.index("        rejected: dict[str, int] = {}\n        cands: list[Candidate] = []")
end = s.index("        scored.sort(key=lambda s: -s[0])")
new = '''        rejected: dict[str, int] = {}
        cands: list[Candidate] = []
        embs = np.zeros((0, hist_emb.shape[1]), dtype=np.float32)
        co_emb = encode([bp.outcomes[slot.co]])[0]
        lo, hi = word_range(slot.marks)
        scored: list = []
        feedback = ""
        for attempt in range(3):          # adaptive resampling: tell the model WHY earlier candidates were rejected
            round_user = user if not feedback else user.replace("Write the question now.", feedback + "\\nWrite the question now.")
            new_cands: list[Candidate] = []
            for j in range(bp.candidates_per_slot):
                try:
                    raw = client.chat_json(prompts.GENERATION_SYSTEM, round_user, temperature=0.85 + 0.1 * attempt,
                                           seed=int(rng.integers(1, 10**6)), max_tokens=500)
                    new_cands.append(Candidate.model_validate(raw))
                except (LLMOutputError, ValidationError, TypeError):
                    rejected["malformed_output"] = rejected.get("malformed_output", 0) + 1
            if not new_cands:
                if attempt == 2 and not cands:
                    raise LLMOutputError(f"No valid candidate for Q{slot.item}{slot.part or ''} after {3 * bp.candidates_per_slot} tries")
                continue
            base = len(cands)
            cands.extend(new_cands)
            new_embs = encode([c.question for c in new_cands])
            embs = np.vstack([embs, new_embs]) if len(embs) else new_embs
            probs = (classifier.predict_proba([c.question for c in cands], [slot.marks] * len(cands))
                     if classifier is not None else None)
            round_reasons: dict[str, int] = {}
            for i in range(base, len(cands)):
                c = cands[i]
                sims = hist_emb @ embs[i]
                j = int(np.argmax(sims))
                max_sim = float(sims[j])
                n_words = len(c.question.split())
                within = max((float(e @ embs[i]) for e in selected_emb), default=0.0)
                reason = None
                if max_sim > bp.novelty_max_similarity or jaccard_3gram(c.question, hist_txt[j]) > 0.45:
                    reason = "not_novel"
                elif _FIGURE_REF.search(c.question):
                    reason = "refers_to_missing_figure"
                elif not (lo <= n_words <= hi):
                    reason = "length_for_marks"
                elif within > 0.72:
                    reason = "duplicate_within_paper"
                if reason:
                    rejected[reason] = rejected.get(reason, 0) + 1
                    round_reasons[reason] = round_reasons.get(reason, 0) + 1
                    continue
                vl = verb_level(c.question)
                p_level = float(probs[i][slot.level - 1]) if probs is not None else 0.0
                # The verb-lexicon check is the deployed level signal: it measurably outperformed every learned
                # classifier on held-out subjects (docs/EVALUATION_BLOOM.md). A learned classifier is used only
                # if one is explicitly supplied.
                verb_fit = 1.0 if vl == slot.level else (0.5 if abs(vl - slot.level) == 1 else 0.0)
                level_fit = (0.6 * p_level + 0.4 * verb_fit) if probs is not None else verb_fit
                topic_fit = float(embs[i] @ cluster.centroid)
                co_fit = float(embs[i] @ co_emb)
                novelty = 1.0 - max_sim
                length_fit = 1.0 if (lo * 1.3 <= n_words <= hi * 0.8) else 0.6
                score = 0.35 * level_fit + 0.25 * max(topic_fit, 0) + 0.15 * max(co_fit, 0) + \\
                    0.15 * min(novelty / 0.4, 1.0) + 0.10 * length_fit
                scored.append((score, i, {"level_fit": level_fit, "topic_fit": topic_fit, "co_fit": co_fit,
                                          "novelty": novelty, "length_fit": length_fit, "total": score},
                               max_sim, hist_ids[j], vl, (int(np.argmax(probs[i])) + 1 if probs is not None else None)))
            if scored:
                break
            feedback = ("Your earlier attempts were REJECTED (" + ", ".join(f"{k}: {v}" for k, v in round_reasons.items()) +
                        "). Write a clearly different question: different sub-topic, different wording, and avoid the themes "
                        "already used in this paper and the reference questions.")
        fallback = False
        if not scored:   # everything filtered after 3 rounds: keep the least-bad candidate but flag it loudly
            fallback = True
            risk = [max(float(np.max(hist_emb @ e)), max((float(x @ e) for x in selected_emb), default=0.0)) for e in embs]
            i = int(np.argmin(risk))
            sims = hist_emb @ embs[i]
            j = int(np.argmax(sims))
            probs = (classifier.predict_proba([c.question for c in cands], [slot.marks] * len(cands))
                     if classifier is not None else None)
            scored = [(0.0, i, {"total": 0.0}, float(sims[j]), hist_ids[j], verb_level(cands[i].question),
                       (int(np.argmax(probs[i])) + 1 if probs is not None else None))]
'''
s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8")
print("patched")
