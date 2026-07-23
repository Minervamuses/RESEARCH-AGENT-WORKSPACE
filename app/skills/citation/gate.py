"""Validate the citation markers that the host renders.

With the citation skill active, ``[[cite:<source-id>]]`` must resolve to a
verified live source and ``[[citation-needed]]`` is the only placeholder.
Without the skill, marker syntax is unavailable because no registry-backed
renderer runs.  Ordinary prose citation styles — DOI, numeric, author-year,
or a handwritten bibliography — are model output and are not policy-gated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MARKER_RE = re.compile(r"\[\[([^\[\]]*)\]\]")
CITE_MARKER_RE = re.compile(r"^cite:(\S+)$")
CITATION_NEEDED = "citation-needed"

_FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


@dataclass(frozen=True)
class GateViolation:
    """One blocking finding; ``code`` is stable for logs and tests."""

    code: str
    detail: str


def _mask_span(text: str, start: int, end: int) -> str:
    return text[:start] + (" " * (end - start)) + text[end:]


def _mask_pattern(text: str, pattern: re.Pattern) -> str:
    out = text
    for match in pattern.finditer(text):
        out = _mask_span(out, match.start(), match.end())
    return out


def mask_unscanned_regions(text: str, *, user_input: str = "") -> str:
    """Blank out code fences and inline code.

    Offsets are preserved (masked regions become spaces) so violation
    details can still reference the original text. Block quotes remain
    scannable because the renderer also transforms markers inside them.
    """
    del user_input  # Kept for the stable gate call signature.
    masked = _mask_pattern(text, _FENCE_RE)
    masked = _mask_pattern(masked, _INLINE_CODE_RE)
    return masked


def check_citations(
    text: str,
    *,
    verified_source_ids: frozenset[str] | set[str],
    citation_active: bool,
    user_input: str = "",
) -> list[GateViolation]:
    """Return every blocking violation in ``text`` (empty list = pass).

    ``citation_active`` selects the policy: active validates markers against
    ``verified_source_ids``; inactive forbids every marker form.
    """
    violations: list[GateViolation] = []
    scannable = mask_unscanned_regions(text or "", user_input=user_input)

    # Active: known forms only, every ID must resolve. Inactive: marker
    # syntax is unavailable because there is no registry-backed renderer.
    for match in MARKER_RE.finditer(scannable):
        body = match.group(1).strip()
        if not citation_active:
            violations.append(GateViolation(
                "citation_inactive_marker",
                f"citation marker [[{body}]] outside the citation skill",
            ))
            continue
        if body == CITATION_NEEDED:
            continue
        cite = CITE_MARKER_RE.match(body)
        if cite:
            if cite.group(1) not in verified_source_ids:
                violations.append(GateViolation(
                    "dangling_cite",
                    f"[[cite:{cite.group(1)}]] does not match any verified source",
                ))
            continue
        violations.append(GateViolation(
            "unknown_marker", f"unrecognized citation marker [[{body}]]"
        ))

    return violations


def build_safe_message(
    violations: list[GateViolation], *, citation_active: bool
) -> str:
    """The user-facing replacement for a blocked draft."""
    lines = [
        "（回應未通過 citation 檢查，已被封鎖。原草稿不會被保存。）",
        "Validation errors:",
    ]
    lines.extend(f"- {v.code}: {v.detail}" for v in violations)
    if citation_active:
        lines.append(
            "請使用目前 registry 中的 [[cite:<source-id>]]；"
            "缺來源的主張可用 [[citation-needed]]。"
        )
    else:
        lines.append(
            "[[cite:...]] 與 [[citation-needed]] 標記僅在 citation skill "
            "啟用時可用（/citation）。"
        )
    return "\n".join(lines)
