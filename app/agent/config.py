"""Agent host settings layered on the framework-neutral RAG configuration."""

from dataclasses import dataclass

from rag.config import RAGConfig

MIN_GRAPH_RECURSION_LIMIT = 3  # Minimum graph steps needed for finalization.


def validate_graph_recursion_limit(value: object) -> int:
    """Return a graph limit that can reach at least one finalization node."""
    if type(value) is not int or value < MIN_GRAPH_RECURSION_LIMIT:
        raise ValueError(
            "graph_recursion_limit must be an integer greater than or equal to "
            f"{MIN_GRAPH_RECURSION_LIMIT}"
        )
    return value


@dataclass
class AgentConfig(RAGConfig):
    """Runtime settings for the agent graph, CLI, and local extensions."""

    # Core runtime
    llm_model: str = "google/gemma-4-26b-a4b-it:free"  # Main chat model.
    llm_max_tokens: int = 4_096  # Main response token cap.
    llm_max_retries: int = 10  # OpenRouter retry count.
    graph_recursion_limit: int = 64  # Per-graph superstep limit.

    # Thinking models
    gen_llm_model: str = "google/gemini-3.1-pro-preview"  # Fusion proposer fallback.
    judge_llm_model: str = "openai/gpt-5.2"  # Fusion aggregator fallback.
    thinking_reviewer_model: str = "anthropic/claude-haiku-4.5"  # Reviewer model.
    thinking_reviewer_max_tokens: int = 4_096  # Reviewer response token cap.
    thinking_rewrite_model: str = "openai/gpt-5-mini"  # Rewrite model.
    thinking_repair_model: str = "openai/gpt-5-mini"  # Repair model.

    # Thinking context
    thinking_tool_trace_chars: int = 500  # Character cap per trace result.
    thinking_tool_trace_total_chars: int = 4_000  # Combined trace character cap.
    thinking_rewrite_visible_chars: int = 2_000  # Visible-context cap for rewrites.
    thinking_rewrite_skill_chars: int = 4_000  # Skill-context cap for rewrites.

    # Thinking fusion
    thinking_fusion_proposer_models: tuple[str, ...] = ()  # Explicit proposer panel.
    thinking_fusion_aggregator_model: str = ""  # Aggregator model override.
    thinking_fusion_aggregator_max_tokens: int = 4_096  # Aggregator response token cap.
    thinking_fusion_candidate_timeout_seconds: float = 180.0  # Per-candidate timeout.
    thinking_fusion_quorum: int = 2  # Required successful candidates.

    # Conversation and logging
    agent_recent_turns_window: int = 10  # Recent turns retained in the prompt.
    plan_logs_dir: str = "plan_logs"  # Legacy Plan-log import root.

    # Skill discovery
    skills_dir: str | None = None  # Skill-root override; None uses app/skills.

    # Extensions
    extension_dropin_dir: str | None = None  # Desired-state root override.
    extension_state_dir: str | None = None  # Validated-state root override.
    extension_max_files: int = 512  # Maximum files per bundle.
    extension_max_file_bytes: int = 8 * 1024 * 1024  # Maximum bytes per file.
    extension_max_bundle_bytes: int = 64 * 1024 * 1024  # Maximum bytes per bundle.

    # Citation output
    citation_output_dir: str | None = None  # Citation-bundle root override.

    # Skill context
    skill_max_pinned_reference_chars: int = 65_536  # Characters per pinned reference.
    skill_max_total_skill_context_chars: int = 200_000  # Total active-skill context chars.

    def __post_init__(self) -> None:
        super().__post_init__()
        validate_graph_recursion_limit(self.graph_recursion_limit)
