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
        version_kind="published",
    )


def test_save_batch_round_trip_is_exact_and_ordered():
    batch = SaveBatchOutcome(
        "b1",
        (
            SaveItemOutcome(1, "second", "not_found", "no_provider_records", alternatives=(SaveAlternative("A Work", year=2020, venue="Venue", version_kind="preprint", doi="10.48550/arxiv.2001.00001", arxiv="2001.00001"),)),
            SaveItemOutcome(0, "first", "saved", "saved_new", receipt()),
        ),
    )
    restored = SaveBatchOutcome.from_artifact(batch.to_artifact())
    assert restored == batch
    assert restored.items[0].alternatives[0].version_kind == "preprint"
    assert restored.items[0].alternatives[0].doi == "10.48550/arxiv.2001.00001"
    assert restored.items[0].alternatives[0].arxiv == "2001.00001"
    assert restored.items[1].receipt.version_kind == "published"


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(extra="x"),
    lambda value: value.update(schema_version=99),
    lambda value: value["items"][0].update(provider_message="arbitrary prose"),
])
def test_save_batch_rejects_unknown_fields_and_schema(mutation):
    artifact = SaveBatchOutcome(
        "b", (SaveItemOutcome(0, "x", "not_found", "no_provider_records"),)
    ).to_artifact()
    mutation(artifact)
    with pytest.raises(ValueError):
        SaveBatchOutcome.from_artifact(artifact)


@pytest.mark.parametrize(("field", "bad_value"), [
    ("request_index", "0"),
    ("requested_label", 7),
    ("reason_code", 7),
])
def test_save_batch_decode_normalizes_bad_item_types_to_value_error(
    field, bad_value,
):
    artifact = SaveBatchOutcome(
        "b", (SaveItemOutcome(0, "x", "not_found", "no_provider_records"),)
    ).to_artifact()
    artifact["items"][0][field] = bad_value

    with pytest.raises(ValueError):
        SaveBatchOutcome.from_artifact(artifact)


def test_save_batch_decode_requires_a_string_batch_id():
    artifact = SaveBatchOutcome(
        "b", (SaveItemOutcome(0, "x", "not_found", "no_provider_records"),)
    ).to_artifact()
    artifact["batch_id"] = 7

    with pytest.raises(ValueError):
        SaveBatchOutcome.from_artifact(artifact)


@pytest.mark.parametrize("target", ["receipt", "alternative"])
def test_save_batch_rejects_unknown_result_version_kind(target):
    batch = SaveBatchOutcome(
        "b",
        (
            SaveItemOutcome(0, "saved", "saved", "saved_new", receipt()),
            SaveItemOutcome(
                1,
                "missing",
                "not_found",
                "no_provider_records",
                alternatives=(SaveAlternative("A Work", version_kind="preprint"),),
            ),
        ),
    ).to_artifact()
    if target == "receipt":
        batch["items"][0]["receipt"]["version_kind"] = "earliest"
    else:
        batch["items"][1]["alternatives"][0]["version_kind"] = "invented"

    with pytest.raises(ValueError, match="version kind"):
        SaveBatchOutcome.from_artifact(batch)


def test_save_batch_requires_items_and_unique_request_indices():
    with pytest.raises(ValueError):
        SaveBatchOutcome("b", ())
    with pytest.raises(ValueError):
        SaveBatchOutcome(
            "b",
            (
                SaveItemOutcome(0, "one", "not_found", "no_provider_records"),
                SaveItemOutcome(0, "two", "not_found", "no_provider_records"),
            ),
        )


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
