"""Parsing and repair heuristics for extended-thinking LLM outputs."""

from __future__ import annotations

import json
import logging
import re
from typing import Sequence, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from agent.llm.text import invoke_text_messages as invoke_text
from agent.thinking.schemas import (
    FusionAggregateResult,
    RevisedDraft,
    ThinkingOutputError,
    _AggregatorResponse,
)

logger = logging.getLogger(__name__)

REVISER_FORMAT_WARNING = (
    "（注意：本次回應的 reviser 輸出格式異常，可能混入內部審稿討論，請斟酌使用。）"
)

_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$",
    re.IGNORECASE | re.DOTALL,
)
_SECTION_MARKER_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(DRAFT|REBUTTAL)[ \t]*:"
    r"(?:\*\*)?[ \t]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_T = TypeVar("_T", bound=BaseModel)


def parse_structured_output(model_type: type[_T], text: str) -> _T:
    """Parse one JSON object into the requested Pydantic model."""
    raw = text.strip()
    fenced = _JSON_FENCE_RE.match(raw)
    if fenced:
        raw = fenced.group("body").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThinkingOutputError(f"invalid JSON from extended thinking step: {exc}") from exc
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise ThinkingOutputError(f"invalid {model_type.__name__}: {exc}") from exc


def parse_aggregate_result(
    text: str,
    *,
    successful_candidate_ids: Sequence[str],
) -> FusionAggregateResult:
    """Parse and validate the aggregator JSON into a FusionAggregateResult.

    Raises :class:`ThinkingOutputError` on invalid JSON, schema violations, a
    blank draft, an unknown candidate id, or selected/dropped overlap. The
    ``reliability_tier`` is left unset; the session control flow owns it.
    """
    raw = text.strip()
    fenced = _JSON_FENCE_RE.match(raw)
    if fenced:
        raw = fenced.group("body").strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThinkingOutputError(f"invalid JSON from aggregator: {exc}") from exc
    if not isinstance(payload, dict):
        raise ThinkingOutputError("aggregator output is not a JSON object")
    try:
        parsed = _AggregatorResponse.model_validate(payload)
    except ValidationError as exc:
        raise ThinkingOutputError(f"invalid aggregator schema: {exc}") from exc

    if not parsed.draft.strip():
        raise ThinkingOutputError("aggregator returned a blank draft")

    valid = set(successful_candidate_ids)
    selected = list(parsed.selected_candidate_ids)
    dropped = list(parsed.dropped_candidate_ids)
    unknown = [cid for cid in (*selected, *dropped) if cid not in valid]
    if unknown:
        raise ThinkingOutputError(
            f"aggregator referenced unknown candidate ids: {', '.join(unknown)}"
        )
    overlap = set(selected) & set(dropped)
    if overlap:
        raise ThinkingOutputError(
            f"aggregator selected and dropped the same candidate ids: "
            f"{', '.join(sorted(overlap))}"
        )

    return FusionAggregateResult(
        draft=parsed.draft,
        selected_candidate_ids=selected,
        dropped_candidate_ids=dropped,
        reliability_tier="",
        summary_for_reviewer=parsed.summary_for_reviewer,
        removed_or_uncertain_points=list(parsed.removed_or_uncertain_points),
        aggregator_error="",
    )


def parse_reviser_output(text: str, *, repair_model=None) -> RevisedDraft:
    """Parse DRAFT/REBUTTAL output with repair and conservative fallbacks."""
    parsed = _parse_marked_reviser_output(text)
    if parsed is not None:
        return parsed

    if repair_model is not None:
        try:
            repaired = invoke_text(
                repair_model,
                [
                    SystemMessage(content=(
                        "Split the following text strictly into two sections marked "
                        "DRAFT: and REBUTTAL:. Preserve the user's visible draft content. "
                        "Move internal disagreement or reviewer discussion into REBUTTAL. "
                        "Return only the two marked sections. "
                        "Preserve the original content's language verbatim—do not translate. "
                        "Keep the marker names themselves in English (DRAFT, REBUTTAL)."
                    )),
                    HumanMessage(content=text),
                ],
            )
            parsed = _parse_marked_reviser_output(repaired)
            if parsed is not None:
                return parsed
            logger.warning("reviser output marker repair failed")
        except Exception as exc:  # pragma: no cover - logging-only safety path
            logger.warning("reviser output marker repair raised: %s", exc)

    stripped = _heuristic_strip_tail(text)
    if stripped is not None:
        return stripped

    logger.error("reviser output marker parsing failed; using whole text as draft")
    return RevisedDraft(
        draft=text.strip(),
        rebuttal="",
        format_warning=REVISER_FORMAT_WARNING,
    )



def _parse_marked_reviser_output(text: str) -> RevisedDraft | None:
    matches = list(_SECTION_MARKER_RE.finditer(text))
    draft_match = next(
        (match for match in matches if match.group(1).casefold() == "draft"),
        None,
    )
    if draft_match is None:
        return None

    rebuttal_match = next(
        (
            match
            for match in matches
            if match.start() > draft_match.start()
            and match.group(1).casefold() == "rebuttal"
        ),
        None,
    )
    draft_end = rebuttal_match.start() if rebuttal_match else len(text)
    draft = _section_text(text, draft_match, draft_end).strip()
    if not draft:
        return None
    if rebuttal_match is None:
        return RevisedDraft(draft=draft, rebuttal="")
    rebuttal = _section_text(text, rebuttal_match, len(text)).strip()
    return RevisedDraft(draft=draft, rebuttal=rebuttal)


def _section_text(text: str, match: re.Match[str], end: int) -> str:
    inline = match.group(2).strip()
    body = text[match.end():end].lstrip("\r\n")
    if inline and body:
        return f"{inline}\n{body}"
    return inline or body


def _heuristic_strip_tail(text: str) -> RevisedDraft | None:
    raw = text.strip()
    if not raw:
        return RevisedDraft(draft="", rebuttal="", format_warning=REVISER_FORMAT_WARNING)
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?=^#{1,6}\s+)", raw, flags=re.MULTILINE)
        if part.strip()
    ]
    if len(paragraphs) <= 1:
        return None

    internal_keywords = (
        "REBUTTAL",
        "rebuttal",
        "駁斥",
        "我不同意",
        "I disagree",
        "Reviewer feedback",
        "Internal note",
        "(none)",
    )
    stripped_parts: list[str] = []
    while paragraphs and any(keyword in paragraphs[-1] for keyword in internal_keywords):
        stripped_parts.insert(0, paragraphs.pop())
    if not stripped_parts:
        return None

    draft = "\n\n".join(paragraphs).strip()
    rebuttal = "\n\n".join(stripped_parts).strip()
    stripped_chars = len(rebuttal)
    if not draft or stripped_chars > len(raw) * 0.5:
        logger.error("reviser heuristic fallback stripped too much internal text")
        return None
    return RevisedDraft(draft=draft, rebuttal=rebuttal)
