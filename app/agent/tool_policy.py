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
) -> list[str]:
    """Return the candidates that survive the policy, preserving input order.

    Invariants shared by every consumer: exact name matching (no base-name
    normalization); an inactive policy admits everything; a non-empty
    allowlist is intersected then reduced by the denylist; a denylist alone
    subtracts; an active policy with both lists empty denies all.
    """
    if not active:
        return list(candidate_names)
    allowed_set = set(allowed or ())
    denied_set = set(denied or ())
    if allowed_set:
        return [
            name
            for name in candidate_names
            if name in allowed_set and name not in denied_set
        ]
    if denied_set:
        return [name for name in candidate_names if name not in denied_set]
    return []
