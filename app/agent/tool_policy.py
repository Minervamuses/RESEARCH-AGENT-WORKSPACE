"""Single source of truth for active-skill tool-policy arithmetic.

Four consumers share this core — graph tool binding, prompt availability
rendering, the fusion proposers' read-only intersection, and PolicyToolNode's
runtime enforcement. Each keeps its own tool universe and presentation; the
allow/deny arithmetic lives here once.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def evaluate_policy(
    candidate_names: Sequence[str],
    *,
    active: bool,
    allowed: Iterable[str] = (),
    denied: Iterable[str] = (),
    skill_only: Iterable[str] = (),
) -> list[str]:
    """Return the candidates that survive the policy, preserving input order.

    Invariants shared by every consumer: exact name matching (no base-name
    normalization); an inactive policy admits every *default* tool; a
    non-empty allowlist is intersected then reduced by the denylist; a
    denylist alone subtracts; an active policy with both lists empty denies
    all.

    ``skill_only`` names are never default tools: they survive only under an
    active policy whose allowlist grants them explicitly. An inactive policy
    or a deny-only policy always drops them, so a skill-only tool can never
    leak into normal mode or into a skill that did not request it.
    """
    skill_only_set = set(skill_only or ())
    if not active:
        return [name for name in candidate_names if name not in skill_only_set]
    allowed_set = set(allowed or ())
    denied_set = set(denied or ())

    def _admitted(name: str) -> bool:
        if name in denied_set:
            return False
        if name in skill_only_set:
            return name in allowed_set
        if allowed_set:
            return name in allowed_set
        return bool(denied_set)

    return [name for name in candidate_names if _admitted(name)]
