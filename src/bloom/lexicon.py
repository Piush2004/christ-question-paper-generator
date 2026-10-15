"""Action-verb lexicon for Revised Bloom's Taxonomy levels (RBT L1..L6).

Used for (a) the rule-based baseline classifier and (b) the generator, which must open each question
with an action verb appropriate to its target level. The lists are standard pedagogical verb
inventories written for this project; they are NOT fitted to the labelled dataset (so the baseline
is not leaking labels).
"""

from __future__ import annotations

import re

LEVEL_NAMES = {1: "Remember", 2: "Understand", 3: "Apply", 4: "Analyse", 5: "Evaluate", 6: "Create"}

VERBS: dict[int, list[str]] = {
    1: ["define", "list", "state", "name", "identify", "recall", "mention", "what", "who", "when", "write",
        "label", "outline", "recognize", "recite", "give"],
    2: ["explain", "describe", "summarize", "summarise", "discuss", "interpret", "classify", "illustrate",
        "elaborate", "paraphrase", "differentiate", "distinguish", "infer", "relate", "why", "how", "elucidate",
        "compare", "contrast"],
    3: ["apply", "solve", "use", "find", "calculate", "compute", "demonstrate", "determine", "construct",
        "show", "implement", "prepare", "draw", "execute", "obtain", "enter", "journalise", "convert",
        "evaluate the value", "simplify"],
    4: ["analyse", "analyze", "examine", "categorize", "categorise", "compare and contrast", "investigate",
        "break down", "differentiate between", "test", "deduce", "organize", "attribute", "trace"],
    5: ["evaluate", "justify", "assess", "judge", "critique", "defend", "verify", "validate", "prove", "argue",
        "recommend", "appraise", "decide"],
    6: ["design", "create", "develop", "generate", "formulate", "compose", "propose", "plan", "devise",
        "sketch", "invent", "build", "synthesize", "synthesise"],
}

_PRIORITY = [6, 5, 4, 3, 1, 2]  # resolve multi-matches toward higher-order verbs, except generic L2 words last


def verb_level(text: str, default: int = 2) -> int:
    """Rule baseline: level of the highest-priority action verb found in the first ~8 words."""
    head = " ".join(re.findall(r"[a-z']+", text.lower())[:8])
    for level in _PRIORITY:
        for v in VERBS[level]:
            if re.search(rf"\b{re.escape(v)}\b", head):
                return level
    return default
