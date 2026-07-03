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
