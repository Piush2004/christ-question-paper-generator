# Generation comparison — measured results (replicated)

Targets (newest paper held out; systems see only the history family): discrete_mathematics [same_course_temporal] history=discrete_mathematics; graph_theory [same_course_temporal] history=graph_theory; psd_2 [related_course_transfer] history=psd_1. RBT mark-share target {'2': 0.3, '3': 0.4, '4': 0.3}. Seeds 7/11/13 (full_no_critic: seed 7 only). Generator `qwen2.5:7b-instruct-q4_K_M`. A *run* = one (system, subject, seed). All LLM responses are recorded in `results/generation/llm_cache.jsonl`, so every run can be replayed exactly.

## same_course_temporal

| system | runs approvable | questions produced/asked | CO coverage | Bloom TV ↓ (mean ± SD over runs) | novelty ↑ | near-copy rate ↓ | LLM-level agreement | format round-trip |
|---|---|---|---|---|---|---|---|---|
| bank_copy | 0/6 | 147/147 | 0.90 ± 0.11 | 0.23 ± 0.09 | -0.00 ± 0.00 | 1.00 ± 0.00 | 0.30 ± 0.09 | 6/6 |
| llm_only | 0/6 | 95/147 | 0.89 ± 0.17 | 0.28 ± 0.08 | 0.50 ± 0.09 | 0.01 ± 0.03 | 0.24 ± 0.16 | 0/6 |
| rag_slots | 1/6 | 147/147 | 1.00 ± 0.00 | 0.14 ± 0.05 | 0.37 ± 0.07 | 0.06 ± 0.06 | 0.49 ± 0.06 | 5/6 |
| full_no_critic | 2/2 | 49/49 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.43 ± 0.03 | 0.00 ± 0.00 | 0.55 ± 0.04 | 2/2 |
| full | 6/6 | 147/147 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.43 ± 0.03 | 0.00 ± 0.00 | 0.52 ± 0.07 | 6/6 |

## related_course_transfer

| system | runs approvable | questions produced/asked | CO coverage | Bloom TV ↓ (mean ± SD over runs) | novelty ↑ | near-copy rate ↓ | LLM-level agreement | format round-trip |
|---|---|---|---|---|---|---|---|---|
| bank_copy | 0/3 | 39/39 | 1.00 ± 0.00 | 0.42 ± 0.09 | -0.00 ± 0.00 | 1.00 ± 0.00 | 0.41 ± 0.12 | 3/3 |
| llm_only | 0/3 | 22/39 | 0.89 ± 0.19 | 0.40 ± 0.10 | 0.54 ± 0.02 | 0.00 ± 0.00 | 0.00 ± 0.00 | 0/3 |
| rag_slots | 1/3 | 39/39 | 1.00 ± 0.00 | 0.16 ± 0.07 | 0.39 ± 0.04 | 0.15 ± 0.08 | 0.62 ± 0.13 | 3/3 |
| full_no_critic | 1/1 | 13/13 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.41 ± 0.00 | 0.00 ± 0.00 | 0.69 ± 0.00 | 1/1 |
| full | 3/3 | 39/39 | 1.00 ± 0.00 | 0.00 ± 0.00 | 0.42 ± 0.01 | 0.00 ± 0.00 | 0.72 ± 0.04 | 3/3 |

## Per run (subject × seed)

| subject | seed | system | approvable | failed hard checks | q | CO cov | Bloom TV | novelty | near-copy | fmt |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete_mathematics | 7 | bank_copy | False | alternatives_same_outcome_level, all_course_outcomes_covered, no_duplicates_within_paper, not_copied_from_history | 24/24 | 0.80 | 0.19 | -0.00 | 1.00 | True |
| discrete_mathematics | 7 | llm_only | False | choice_items, alternatives_same_outcome_level | 18/24 | 1.00 | 0.26 | 0.52 | 0.00 | False |
| discrete_mathematics | 7 | rag_slots | True | - | 24/24 | 1.00 | 0.08 | 0.46 | 0.04 | True |
| discrete_mathematics | 7 | full_no_critic | True | - | 24/24 | 1.00 | 0.00 | 0.45 | 0.00 | True |
| discrete_mathematics | 7 | full | True | - | 24/24 | 1.00 | 0.00 | 0.45 | 0.00 | True |
| discrete_mathematics | 11 | bank_copy | False | alternatives_same_outcome_level, all_course_outcomes_covered, no_duplicates_within_paper, not_copied_from_history | 24/24 | 0.80 | 0.14 | -0.00 | 1.00 | True |
| discrete_mathematics | 11 | llm_only | False | items_per_section, choice_items, total_marks | 18/24 | 1.00 | 0.19 | 0.59 | 0.00 | False |
| discrete_mathematics | 11 | rag_slots | False | no_duplicates_within_paper | 24/24 | 1.00 | 0.12 | 0.41 | 0.00 | True |
| discrete_mathematics | 11 | full | True | - | 24/24 | 1.00 | 0.00 | 0.48 | 0.00 | True |
| discrete_mathematics | 13 | bank_copy | False | alternatives_same_outcome_level, all_course_outcomes_covered, no_duplicates_within_paper, not_copied_from_history | 24/24 | 0.80 | 0.12 | -0.00 | 1.00 | True |
| discrete_mathematics | 13 | llm_only | False | choice_items | 17/24 | 1.00 | 0.24 | 0.60 | 0.00 | False |
| discrete_mathematics | 13 | rag_slots | False | self_contained | 24/24 | 1.00 | 0.10 | 0.43 | 0.00 | True |
| discrete_mathematics | 13 | full | True | - | 24/24 | 1.00 | 0.00 | 0.44 | 0.00 | True |
| graph_theory | 7 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 25/25 | 1.00 | 0.32 | -0.00 | 1.00 | True |
| graph_theory | 7 | llm_only | False | items_per_section, choice_items, total_marks, alternatives_same_outcome_level, all_course_outcomes_covered | 28/25 | 0.67 | 0.23 | 0.38 | 0.07 | False |
| graph_theory | 7 | rag_slots | False | self_contained, no_duplicates_within_paper | 25/25 | 1.00 | 0.21 | 0.32 | 0.08 | True |
| graph_theory | 7 | full_no_critic | True | - | 25/25 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| graph_theory | 7 | full | True | - | 25/25 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| graph_theory | 11 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 25/25 | 1.00 | 0.27 | -0.00 | 1.00 | True |
| graph_theory | 11 | llm_only | False | items_per_section, choice_items, total_marks | 11/25 | 1.00 | 0.36 | 0.45 | 0.00 | False |
| graph_theory | 11 | rag_slots | False | self_contained, no_duplicates_within_paper, not_copied_from_history | 25/25 | 1.00 | 0.13 | 0.31 | 0.12 | True |
| graph_theory | 11 | full | True | - | 25/25 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| graph_theory | 13 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 25/25 | 1.00 | 0.33 | -0.00 | 1.00 | True |
| graph_theory | 13 | llm_only | False | items_per_section, choice_items, total_marks, all_course_outcomes_covered | 3/25 | 0.67 | 0.40 | 0.44 | 0.00 | False |
| graph_theory | 13 | rag_slots | False | question_length, self_contained, non_empty, no_duplicates_within_paper, not_copied_from_history | 25/25 | 1.00 | 0.17 | 0.31 | 0.12 | False |
| graph_theory | 13 | full | True | - | 25/25 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| psd_2 | 7 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 13/13 | 1.00 | 0.32 | -0.00 | 1.00 | True |
| psd_2 | 7 | llm_only | False | items_per_section, choice_items, total_marks | 10/13 | 1.00 | 0.49 | 0.53 | 0.00 | False |
| psd_2 | 7 | rag_slots | True | - | 13/13 | 1.00 | 0.08 | 0.41 | 0.08 | True |
| psd_2 | 7 | full_no_critic | True | - | 13/13 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| psd_2 | 7 | full | True | - | 13/13 | 1.00 | 0.00 | 0.41 | 0.00 | True |
| psd_2 | 11 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 13/13 | 1.00 | 0.48 | -0.00 | 1.00 | True |
| psd_2 | 11 | llm_only | False | items_per_section, total_marks, alternatives_same_outcome_level | 10/13 | 1.00 | 0.30 | 0.53 | 0.00 | False |
| psd_2 | 11 | rag_slots | False | no_duplicates_within_paper | 13/13 | 1.00 | 0.18 | 0.42 | 0.15 | True |
| psd_2 | 11 | full | True | - | 13/13 | 1.00 | 0.00 | 0.42 | 0.00 | True |
| psd_2 | 13 | bank_copy | False | alternatives_same_outcome_level, no_duplicates_within_paper, not_copied_from_history | 13/13 | 1.00 | 0.46 | -0.00 | 1.00 | True |
| psd_2 | 13 | llm_only | False | items_per_section, choice_items, total_marks, alternatives_same_outcome_level, all_course_outcomes_covered | 2/13 | 0.67 | 0.40 | 0.55 | 0.00 | False |
| psd_2 | 13 | rag_slots | False | no_duplicates_within_paper, not_copied_from_history | 13/13 | 1.00 | 0.22 | 0.35 | 0.23 | True |
| psd_2 | 13 | full | True | - | 13/13 | 1.00 | 0.00 | 0.43 | 0.00 | True |

## Questions flagged for teacher attention (every candidate failed a check)

- full: 5 flagged over 9 runs (186 questions)
- full_no_critic: 0 flagged over 3 runs (62 questions)

## DIAGNOSTIC ONLY — LLM-judge scores (1–5, same 7B model; NOT human ratings, NOT quality evidence)

| system | clarity | answerable | syllabus fit |
|---|---|---|---|
| bank_copy | 2.82 | 2.99 | 3.73 |
| llm_only | 3.57 | 4.36 | 4.69 |
| rag_slots | 3.68 | 4.27 | 4.54 |
| full_no_critic | 3.81 | 4.21 | 4.66 |
| full | 3.89 | 4.38 | 4.78 |
| *real held-out faculty questions* | 2.91 | 3.26 | 4.11 |

The judge scores real faculty questions below every generated paper, so it rewards LLM-style prose rather than assessment quality.