"""Paper-level multi-objective optimizer interface (master-prompt §34, Phase 0.5 §22).

Architecture decision already recorded (docs/ARCHITECTURE.md): CP-SAT (OR-Tools, already in
requirements.txt and verified importable — see docs/ENVIRONMENT_AUDIT.md) for the constraint solver.
This interface exists so the blueprint-compilation and candidate-ranking stages have a stable contract
to build against, without the solver itself needing to exist yet.

Not implemented yet: needs a compiled blueprint (src/blueprint/) and ranked, scored candidates
(src/generation/, src/novelty/, plus the future candidate ranker) as real input — there is nothing to
optimize over until those exist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.utils.not_implemented import ComponentNotYetAvailableError


@dataclass
class OptimizationResult:
    status: str  # "FEASIBLE" | "INFEASIBLE"
    selected_question_ids: list[str]
    objective_value: float | None
    infeasibility_reason: str | None  # populated when status == "INFEASIBLE" (§31: never silently violate constraints)


class PaperOptimizer(ABC):
    @abstractmethod
    def optimize(self, candidate_pool_ids: list[str]) -> OptimizationResult:
        """Select a constraint-satisfying, objective-maximizing subset of candidates for the final
        paper. On infeasibility, MUST return status="INFEASIBLE" with a human-readable reason and a
        suggested correction (§31) — never silently drop a hard constraint to force a solution."""


class NotYetAvailablePaperOptimizer(PaperOptimizer):
    def optimize(self, candidate_pool_ids: list[str]) -> OptimizationResult:
        raise ComponentNotYetAvailableError(
            "PaperOptimizer",
            "no compiled blueprint or scored candidate pool exists yet to optimize over.",
        )
