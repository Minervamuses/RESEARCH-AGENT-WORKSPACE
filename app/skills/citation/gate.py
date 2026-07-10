"""Final citation gate for assistant drafts — two explicit policies.

Citation skill ACTIVE: the model may cite verified sources through
``[[cite:<source-id>]]`` markers (with ``[[citation-needed]]`` as the one
placeholder); dangling IDs and unknown marker forms block.

Citation skill INACTIVE: formal citations are forbidden outright — every
``[[...]]`` marker (including ``citation-needed``) blocks, alongside the
always-forbidden raw forms.

Both policies, after Markdown-aware masking (code fences, inline code, and
block quotes provably taken from the user's input are not scanned), block
raw DOIs, raw numeric citations, raw author-year citations, and handwritten
bibliographies. No model call is made to repair a violating draft; the
caller replaces it with a safe message and the draft never reaches history
or the plan log.

Ordinary Markdown web links (without DOIs) are allowed in both policies:
they are never numbered, never become SourceRefs, and never enter the
bibliography.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from skills.citation.doi import extract_doi_candidates

MARKER_RE = re.compile(r"\[\[([^\[\]]*)\]\]")
CITE_MARKER_RE = re.compile(r"^cite:(\S+)$")
CITATION_NEEDED = "citation-needed"

_FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_MD_LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
_NUMERIC_CITATION_RE = re.compile(r"\[(\d{1,3})\](?!\()")
_AUTHOR_YEAR_RES = (
    # (Vaswani et al., 2017) / (Smith, 2020) / (Smith and Jones 2020)
    re.compile(
        r"\((?:e\.g\.,?\s*)?[A-Z][\w\-]+(?:\s+(?:et\s+al\.?|&\s*[A-Z][\w\-]+|and\s+[A-Z][\w\-]+))?"
        r",?\s+(?:19|20)\d{2}[a-z]?\)"
    ),
    # Vaswani et al. (2017)
    re.compile(r"\b[A-Z][\w\-]+\s+et\s+al\.?\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)"),
)
_BIBLIOGRAPHY_HEADING_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?(?:\*\*)?\s*"
    r"(references|bibliography|works\s+cited|參考文獻|引用文獻|参考文献)"
    r"\s*(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


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


def _normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _mask_user_quotes(text: str, user_input: str) -> str:
    """Mask block-quote runs whose content provably appears in user input."""
    if not user_input:
        return text
    normalized_user = _normalize_quote(user_input)
    lines = text.split("\n")
    masked_lines = list(lines)
    block: list[int] = []

    def _flush(indices: list[int]) -> None:
        if not indices:
            return
        content = _normalize_quote(
            " ".join(re.sub(r"^\s{0,3}>\s?", "", lines[i]) for i in indices)
        )
        if content and content in normalized_user:
            for i in indices:
                masked_lines[i] = " " * len(lines[i])

    for i, line in enumerate(lines):
        if re.match(r"^\s{0,3}>", line):
            block.append(i)
        else:
            _flush(block)
            block = []
    _flush(block)
    return "\n".join(masked_lines)


def mask_unscanned_regions(text: str, *, user_input: str = "") -> str:
    """Blank out code fences, inline code, and provable user quotes.

    Offsets are preserved (masked regions become spaces) so violation
    details can still reference the original text.
    """
    masked = _mask_pattern(text, _FENCE_RE)
    masked = _mask_pattern(masked, _INLINE_CODE_RE)
    masked = _mask_user_quotes(masked, user_input)
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

    # 1. Markers. Active: known forms only, every ID must resolve.
    #    Inactive: no marker of any form may appear.
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
    marker_free = _mask_pattern(scannable, MARKER_RE)

    # 2. Raw DOIs anywhere scannable — including inside Markdown links.
    for doi in extract_doi_candidates(marker_free):
        violations.append(GateViolation(
            "raw_doi",
            f"raw DOI {doi!r} in prose; only verified [[cite:...]] markers "
            "may reference sources",
        ))
        break  # one finding is enough to block; details stay short

    # 3. Raw numeric citations like [1] (link labels [text](url) excluded).
    link_free = _mask_pattern(marker_free, _MD_LINK_RE)
    numeric = _NUMERIC_CITATION_RE.search(link_free)
    if numeric:
        violations.append(GateViolation(
            "raw_numeric_citation",
            f"raw numeric citation {numeric.group(0)!r}; numbering is assigned "
            "by the renderer, not the model",
        ))

    # 4. Raw author-year citations.
    for pattern in _AUTHOR_YEAR_RES:
        match = pattern.search(link_free)
        if match:
            violations.append(GateViolation(
                "raw_author_year",
                f"raw author-year citation {match.group(0)!r}",
            ))
            break

    # 5. Handwritten bibliography sections.
    if _BIBLIOGRAPHY_HEADING_RE.search(link_free):
        violations.append(GateViolation(
            "handwritten_bibliography",
            "a References/Bibliography section may only be produced by the renderer",
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
            "請先在 citation workflow 中完成驗證（搜尋→選擇→確認），"
            "再以 [[cite:<source-id>]] 引用；缺來源的主張用 [[citation-needed]]。"
        )
    else:
        lines.append(
            "正式引用僅在 citation skill 啟用時可用（/citation）；"
            "一般非 DOI 網址連結不受此限制。"
        )
    return "\n".join(lines)
