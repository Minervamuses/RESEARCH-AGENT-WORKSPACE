"""Structured helpers for the optional extended thinking workflow.

Split into schemas / prompts / parsers / review / trace; this package
re-exports the former flat module's names so importers are unchanged.
"""

from agent.llm.text import invoke_text_messages as invoke_text
from agent.thinking.parsers import (
    REVISER_FORMAT_WARNING,
    extract_draft_for_user,
    parse_aggregate_result,
    parse_reviser_output,
    parse_structured_output,
)
from agent.thinking.prompts import (
    aggregate_messages,
    review_messages,
    rewrite_messages,
)
from agent.thinking.review import (
    MAX_REVIEW_ATTEMPTS,
    aggregate_candidates,
    render_review_stop_message,
    render_route_message,
    review_draft,
    rewrite_prompt,
    route_review_report,
)
from agent.thinking.schemas import (
    Clarify,
    FusionAggregateResult,
    FusionCandidate,
    FusionCandidateStatus,
    FusionCandidateTrace,
    FusionReliabilityTier,
    FusionTurnMetadata,
    ReviewDecision,
    ReviewFailureMode,
    ReviewFinding,
    ReviewReport,
    ReviewRoute,
    ReviewSeverity,
    RevisedDraft,
    Rewrite,
    RewriteResult,
    ThinkingOutputError,
)
from agent.thinking.trace import (
    append_tool_trace,
    build_fusion_evidence_summary,
    summarize_tool_trace,
    trim_head,
    trim_tail,
)

__all__ = [
    "MAX_REVIEW_ATTEMPTS",
    "REVISER_FORMAT_WARNING",
    "Clarify",
    "FusionAggregateResult",
    "FusionCandidate",
    "FusionCandidateStatus",
    "FusionCandidateTrace",
    "FusionReliabilityTier",
    "FusionTurnMetadata",
    "ReviewDecision",
    "ReviewFailureMode",
    "ReviewFinding",
    "ReviewReport",
    "ReviewRoute",
    "ReviewSeverity",
    "RevisedDraft",
    "Rewrite",
    "RewriteResult",
    "ThinkingOutputError",
    "aggregate_candidates",
    "aggregate_messages",
    "append_tool_trace",
    "build_fusion_evidence_summary",
    "extract_draft_for_user",
    "invoke_text",
    "parse_aggregate_result",
    "parse_reviser_output",
    "parse_structured_output",
    "render_review_stop_message",
    "render_route_message",
    "review_draft",
    "review_messages",
    "rewrite_messages",
    "rewrite_prompt",
    "route_review_report",
    "summarize_tool_trace",
    "trim_head",
    "trim_tail",
]
