"""Data contracts for the extended thinking workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

FusionCandidateStatus = Literal["success", "failed", "timeout", "empty"]
FusionReliabilityTier = Literal[
    "full_panel",
    "partial_panel",
    "single_candidate",
    "fallback",
]

ReviewSeverity = Literal["blocker", "major", "minor", "note"]
ReviewDecision = Literal["pass", "revise", "block"]
ReviewRoute = Literal["pass", "revise", "ask_user", "stop"]
ReviewFailureMode = Literal[
    "retrieval_not_attempted",
    "retrieval_empty",
    "tool_unavailable",
    "user_input_missing",
    "fabrication_risk",
]


class ThinkingOutputError(ValueError):
    """Raised when an extended-thinking LLM step returns invalid structured output."""


class Clarify(BaseModel):
    """Prompt rewrite result asking the user for missing information."""

    text: str


class Rewrite(BaseModel):
    """Prompt rewrite result containing a clarified agent prompt."""

    prompt: str


RewriteResult = Clarify | Rewrite


class ReviewFinding(BaseModel):
    severity: ReviewSeverity
    dimension: str
    location: str
    problem: str
    evidence_from_draft: str
    revision_instruction: str
    needs_user_input: bool
    failure_mode: ReviewFailureMode | None = None


class ReviewReport(BaseModel):
    decision: ReviewDecision
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary_for_reviser: str


class RevisedDraft(BaseModel):
    draft: str
    rebuttal: str = ""
    format_warning: str = ""


@dataclass(frozen=True)
class FusionCandidate:
    """One proposer graph result in the extended-thinking fusion panel."""

    candidate_id: str
    model_id: str
    status: FusionCandidateStatus
    answer: str
    tool_trace_summary: str
    error: str = ""
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class FusionCandidateTrace:
    """Per-candidate segmented trace; kept separate so tool_call_ids never cross."""

    candidate_id: str
    model_id: str
    status: FusionCandidateStatus
    new_messages: list = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    trace_events: list[dict] = field(default_factory=list)
    tool_trace_summary: str = ""
    answer_excerpt: str = ""


@dataclass
class FusionAggregateResult:
    """Session-level aggregate result over the successful candidate panel."""

    draft: str
    selected_candidate_ids: list[str] = field(default_factory=list)
    dropped_candidate_ids: list[str] = field(default_factory=list)
    reliability_tier: FusionReliabilityTier | str = ""
    summary_for_reviewer: str = ""
    removed_or_uncertain_points: list[str] = field(default_factory=list)
    aggregator_error: str = ""


@dataclass
class FusionTurnMetadata:
    """Compact, JSON-serializable fusion metadata for one extended turn."""

    candidate_statuses: dict[str, str] = field(default_factory=dict)
    model_ids: dict[str, str] = field(default_factory=dict)
    selected_ids: list[str] = field(default_factory=list)
    dropped_ids: list[str] = field(default_factory=list)
    omitted_successful_ids: list[str] = field(default_factory=list)
    reliability_tier: str = ""
    aggregator_error: str = ""
    quorum: int = 0
    resolved_proposer_models: list[str] = field(default_factory=list)
    resolved_aggregator_model: str = ""

    def to_dict(self) -> dict:
        """Return a plain dict suitable for turn logs and trace events."""
        return asdict(self)


class _AggregatorResponse(BaseModel):
    """Raw JSON contract returned by the aggregator LLM."""

    draft: str
    selected_candidate_ids: list[str] = Field(default_factory=list)
    dropped_candidate_ids: list[str] = Field(default_factory=list)
    summary_for_reviewer: str = ""
    removed_or_uncertain_points: list[str] = Field(default_factory=list)
