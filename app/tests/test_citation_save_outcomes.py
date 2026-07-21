from dataclasses import replace

import pytest

from skills.citation.registry import SourceRegistry
from skills.citation.types import (
    CanonicalIdentity,
    SaveAlternative,
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    SourceRef,
)


def receipt():
    return SaveReceipt(
        source_id="src-abc",
        canonical_identity=CanonicalIdentity("doi", "10.1234/work"),
        doi="10.1234/work",
        title="A Work",
        year=2020,
        work_type="journal-article",
        bundle_path="/tmp/cite/a",
        verification_level="doi_identity_verified",
        cite_marker="[[cite:src-abc]]",
    )


def test_save_batch_round_trip_is_exact_and_ordered():
    batch = SaveBatchOutcome(
        "b1", "attempted", "none",
        (
            SaveItemOutcome(1, "second", "ambiguous", "version_clarification_required", alternatives=(SaveAlternative("A Work", year=2020, venue="Venue", version_kind="published"),)),
            SaveItemOutcome(0, "first", "saved", "saved_new", receipt()),
        ),
    )
    assert SaveBatchOutcome.from_artifact(batch.to_artifact()) == batch


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(extra="x"),
    lambda value: value.update(schema_version=99),
    lambda value: value["items"][0].update(provider_message="arbitrary prose"),
])
def test_save_batch_rejects_unknown_fields_and_schema(mutation):
    artifact = SaveBatchOutcome("b", "attempted", "none", (SaveItemOutcome(0, "x", "not_found", "no_provider_records"),)).to_artifact()
    mutation(artifact)
    with pytest.raises(ValueError):
        SaveBatchOutcome.from_artifact(artifact)


def test_rejected_batch_contract_is_strict():
    assert SaveBatchOutcome.from_artifact(SaveBatchOutcome("b", "rejected", "workflow_busy").to_artifact()).items == ()
    with pytest.raises(ValueError):
        SaveBatchOutcome("b", "rejected", "none")
    with pytest.raises(ValueError):
        SaveBatchOutcome("b", "attempted", "none")


def test_registry_collision_preserves_original_source():
    registry = SourceRegistry()
    first = SourceRef("src-same", "10.1234/one", "One")
    registry.register(first)
    with pytest.raises(ValueError):
        registry.register(SourceRef("src-same", "10.1234/two", "Two"))
    assert registry.get("src-same") is first


def test_registry_binds_and_revalidates_trusted_save_receipt():
    registry = SourceRegistry()
    ref = SourceRef(
        "src-abc", "10.1234/work", "A Work", year=2020,
        work_type="journal-article", schema_version=2,
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.1234/work"),
    )
    trusted = receipt()

    registry.register(ref, receipt=trusted)

    assert registry.trusted_receipt(ref.source_id) == trusted
    assert registry.receipt_is_trusted(trusted)

    ref.title = "Mutated title"
    assert not registry.receipt_is_trusted(trusted)


def test_registry_rejects_mismatched_receipt_and_clears_stale_trust():
    registry = SourceRegistry()
    ref = SourceRef(
        "src-abc", "10.1234/work", "A Work", year=2020,
        work_type="journal-article", schema_version=2,
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.1234/work"),
    )
    mismatched = replace(receipt(), title="Another Work")

    with pytest.raises(ValueError, match="does not match source"):
        registry.register(ref, receipt=mismatched)
    assert registry.get(ref.source_id) is None

    registry.register(ref, receipt=receipt())
    registry.register(ref)
    assert registry.trusted_receipt(ref.source_id) is None
