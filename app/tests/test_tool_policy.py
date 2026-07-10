"""Tests for the shared tool-policy core used by all four policy consumers."""

from agent.tool_policy import evaluate_policy

UNIVERSE = ["rag_search", "rag_get_context", "read_file", "bash"]


def test_inactive_policy_admits_everything_in_order():
    assert evaluate_policy(UNIVERSE, active=False) == UNIVERSE
    assert evaluate_policy(
        UNIVERSE, active=False, allowed=["bash"], denied=["rag_search"],
    ) == UNIVERSE


def test_allowlist_intersects_then_subtracts_denylist():
    assert evaluate_policy(
        UNIVERSE,
        active=True,
        allowed=["read_file", "rag_search", "not_in_universe"],
        denied=["read_file"],
    ) == ["rag_search"]


def test_denylist_alone_subtracts():
    assert evaluate_policy(
        UNIVERSE, active=True, denied=["bash", "read_file"],
    ) == ["rag_search", "rag_get_context"]


def test_active_with_both_lists_empty_denies_all():
    assert evaluate_policy(UNIVERSE, active=True) == []
    assert evaluate_policy(UNIVERSE, active=True, allowed=(), denied=()) == []


def test_exact_name_matching_no_normalization():
    assert evaluate_policy(
        ["rag_search", "rag_search_v2"], active=True, allowed=["rag_search"],
    ) == ["rag_search"]


def test_preserves_candidate_order_not_allowlist_order():
    assert evaluate_policy(
        UNIVERSE, active=True, allowed=["bash", "rag_search"],
    ) == ["rag_search", "bash"]


SKILL_UNIVERSE = [*UNIVERSE, "citation_workflow"]


def test_skill_only_tool_never_survives_inactive_policy():
    assert evaluate_policy(
        SKILL_UNIVERSE, active=False, skill_only=["citation_workflow"],
    ) == UNIVERSE
    # Even an (ignored) allowlist naming it does not resurrect it.
    assert evaluate_policy(
        SKILL_UNIVERSE,
        active=False,
        allowed=["citation_workflow"],
        skill_only=["citation_workflow"],
    ) == UNIVERSE


def test_skill_only_tool_requires_explicit_allowlist_grant():
    assert evaluate_policy(
        SKILL_UNIVERSE,
        active=True,
        allowed=["citation_workflow"],
        skill_only=["citation_workflow"],
    ) == ["citation_workflow"]
    # A deny-only policy admits defaults but never the skill-only tool.
    assert evaluate_policy(
        SKILL_UNIVERSE,
        active=True,
        denied=["bash"],
        skill_only=["citation_workflow"],
    ) == ["rag_search", "rag_get_context", "read_file"]


def test_skill_only_tool_still_subject_to_denylist():
    assert evaluate_policy(
        SKILL_UNIVERSE,
        active=True,
        allowed=["citation_workflow"],
        denied=["citation_workflow"],
        skill_only=["citation_workflow"],
    ) == []
