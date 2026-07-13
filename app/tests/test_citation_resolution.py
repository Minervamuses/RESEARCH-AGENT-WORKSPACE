import json
from pathlib import Path

import pytest

from skills.citation.providers.base import ProviderRecord
from skills.citation.resolution import (
    HostIntentBinder,
    HostIntentClaim,
    WorkConstraint,
    WorkIdentifier,
    WorkIntent,
    decide_resolution,
    evaluate_record,
)


def _hard(field, value):
    return WorkConstraint(
        field, value,
        provenance="explicit_current_user",
        requested_strength="hard",
        effective_provenance="explicit_current_user",
        effective_strength="hard",
        host_verified=True,
    )


@pytest.mark.parametrize("case", json.loads(
    (Path(__file__).parent / "fixtures/citation_resolution_cases.json").read_text()
))
def test_resolution_corpus(case):
    raw_intent = case["intent"]
    constraints = ()
    if raw_intent.get("work_kind"):
        constraints = (_hard("work_kind", raw_intent["work_kind"]),)
    identifiers = ()
    if raw_intent.get("doi"):
        identifiers = (WorkIdentifier("doi", raw_intent["doi"]),)
    intent = WorkIntent(
        requested_label=case["name"],
        title=raw_intent["title"],
        authors=tuple(raw_intent.get("authors", [])),
        year=raw_intent.get("year"),
        identifiers=identifiers,
        constraints=constraints,
    )
    record = ProviderRecord("fixture", "fixture:1", 0, **case["record"])
    decision = evaluate_record(intent, record)
    assert decision.status == case["status"]
    assert decision.reason_code == case["reason"]


def test_exact_identifier_does_not_override_title_conflict():
    intent = WorkIntent("wanted", title="Right work", identifiers=(WorkIdentifier("doi", "10.1000/abc"),))
    record = ProviderRecord("x", "x:1", 0, title="Entirely different", doi="10.1000/abc")
    decision = evaluate_record(intent, record)
    assert decision.status == "identity_conflict"
    assert decision.reason_code == "title_mismatch"


def test_generic_reference_with_two_versions_requires_clarification():
    intent = WorkIntent("這篇", title="A Work", authors=("An Author",))
    records = [
        ProviderRecord("x", "x:published", 0, title="A Work", authors=["An Author"], doi="10.1000/pub", venue="Venue"),
        ProviderRecord("x", "x:preprint", 1, title="A Work", authors=["An Author"], doi="10.1000/pre", work_type="preprint"),
    ]
    decision = decide_resolution(intent, records)
    assert decision.status == "ambiguous"
    assert decision.reason_code == "version_clarification_required"


def test_unqualified_original_requires_semantic_disambiguation():
    intent = WorkIntent("original", title="A Work")
    result = HostIntentBinder().bind([intent], [HostIntentClaim("original", "original")])
    assert result.ambiguous
    assert result.reason_code == "intent_binding_ambiguous"


def test_only_host_verified_hard_constraint_can_veto():
    record = ProviderRecord("x", "x:1", 0, title="A Work", year=2020)
    visible = WorkConstraint("year", "2017")
    assert evaluate_record(WorkIntent("x", title="A Work", constraints=(visible,)), record).status == "eligible"
    assert evaluate_record(WorkIntent("x", title="A Work", constraints=(_hard("year", "2017"),)), record).status == "identity_conflict"


def test_binder_injects_single_item_claim_and_rejects_unbound_multi_item_claim():
    binder = HostIntentBinder()
    one = binder.bind([WorkIntent("one", title="One")], [HostIntentClaim("year", "2020")])
    assert one.intents[0].constraints[0].is_hard
    multi = binder.bind(
        [WorkIntent("one", title="One"), WorkIntent("two", title="Two")],
        [HostIntentClaim("year", "2020")],
    )
    assert multi.ambiguous
    assert all(i.binding_reason == "intent_binding_ambiguous" for i in multi.intents)


def test_negative_target_never_becomes_eligible():
    result = HostIntentBinder().bind(
        [WorkIntent("one", title="One")],
        [HostIntentClaim("year", "2020", polarity="negative")],
    )
    assert evaluate_record(result.intents[0], ProviderRecord("x", "x:1", 0, title="One")).status == "insufficient_intent"


def test_bounds_are_strict():
    with pytest.raises(ValueError):
        WorkIntent("x", title="a" * 513)
    with pytest.raises(ValueError):
        WorkIdentifier("doi", "c1")
