"""Shared "not yet available" signaling for future ML components (Phase 0.5 §22).

Master-prompt Rule 66 forbids mocking core ML behavior (no `bloom = "Apply"`, no
`quality = random.choice(...)`). The corollary for components that genuinely don't exist yet is:
they must say so explicitly, loudly, and the same way every time — never return a plausible-looking
but fabricated value. Every future-component interface in src/bloom/, src/dok/, src/difficulty/,
src/generation/, src/novelty/, src/optimization/ raises this from its default (not-yet-implemented)
implementation.
"""

from __future__ import annotations


class ComponentNotYetAvailableError(NotImplementedError):
    """Raised by a not-yet-implemented ML component's interface methods.

    This is deliberately loud and specific rather than a bare NotImplementedError, so a caller
    catching exceptions broadly still gets an unambiguous, greppable signal that the correct
    response is "this research phase hasn't started," not "this call failed."
    """

    def __init__(self, component_name: str, reason: str):
        super().__init__(
            f"{component_name} is not yet implemented — {reason} "
            "See docs/RESEARCH_GAP.md and docs/RESEARCH_DECISION_LOG.md for sequencing; "
            "this component is scheduled for a later phase, once its prerequisites exist."
        )
