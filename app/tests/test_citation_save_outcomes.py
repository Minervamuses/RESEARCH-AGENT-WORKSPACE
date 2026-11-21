import asyncio
import json as _json
from dataclasses import replace

import pytest

from skills.citation.gate import check_citations
from skills.citation.hub import CitationProviderHub
from skills.citation.library import load as _load_library
from skills.citation.providers.net import FetchResponse
from skills.citation.registry import SourceRegistry
from skills.citation.resolution import WorkIdentifier, WorkIntent
from skills.citation.service import CitationService
from skills.citation.types import (
    CanonicalIdentity,
    SaveAlternative,
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    SourceRef,
    is_citable_source,
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


# --- Verification guarantees that do not depend on the BibTeX chain -------
#
# These saves run in desktop mode (a project bibliography), whose success
# status is ``saved`` before and after the BibTeX chain is removed.

_REQUESTED_ALIAS_DOI = "10.5555/alias-of-primary"
_PRIMARY_DOI = "10.5555/primary-work"
_NORMAL_DOI = "10.5555/normal-work"
_ARXIV_ATOM = (
    b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
    b"<id>http://arxiv.org/abs/2001.00001v1</id><title>A Preprint</title>"
    b"<published>2020-01-02T00:00:00Z</published>"
    b"<author><name>Ada Author</name></author></entry></feed>"
)


def _csl(doi, title):
    return {
        "DOI": doi, "title": title, "author": [{"given": "Kim", "family": "Ng"}],
        "issued": {"date-parts": [[2021]]}, "type": "journal-article",
        "container-title": "Journal",
    }


async def _verification_fetcher(url, headers):
    accept = headers.get("Accept", "")
    if url.startswith("https://export.arxiv.org/api/query?"):
        return FetchResponse(200, body=_ARXIV_ATOM)
    doi = url.removeprefix("https://doi.org/")
    # doi.org answers an alias DOI with the primary work's metadata.
    canonical = _PRIMARY_DOI if doi == _REQUESTED_ALIAS_DOI else doi
    if canonical not in {_PRIMARY_DOI, _NORMAL_DOI}:
        raise AssertionError(f"unexpected url: {url}")
    title = "Primary Work" if canonical == _PRIMARY_DOI else "Normal Work"
    if "csl+json" in accept:
        return FetchResponse(200, body=_json.dumps(_csl(canonical, title)).encode())
    if "x-bibtex" in accept:
        return FetchResponse(200, body=(
            f"@article{{k, title={{{title}}}, author={{Ng, Kim}}, year={{2021}}, doi={{{canonical}}}}}"
        ).encode())
    raise AssertionError(f"unexpected accept header: {accept}")


def _desktop_service(tmp_path):
    return CitationService(
        CitationProviderHub(env={}, fetcher=_verification_fetcher),
        output_dir=tmp_path / "cite",
        library_path=tmp_path / "references.json",
    )


def _assert_citable(service, receipt):
    ref = service.registry.get(receipt.source_id)
    assert ref is not None and is_citable_source(ref)
    assert check_citations(
        receipt.cite_marker,
        verified_source_ids={receipt.source_id},
        citation_active=True,
    ) == []


def test_normal_doi_and_arxiv_saves_succeed(tmp_path):
    service = _desktop_service(tmp_path)
    outcome = asyncio.run(service.save((
        WorkIntent("doi pick", identifiers=(WorkIdentifier("doi", _NORMAL_DOI),)),
        WorkIntent("arxiv pick", identifiers=(WorkIdentifier("arxiv", "2001.00001"),)),
    )))

    doi_item, arxiv_item = outcome.items
    assert (doi_item.status, doi_item.reason_code) == ("saved", "saved_new")
    assert doi_item.receipt.canonical_identity.key == _NORMAL_DOI
    assert doi_item.receipt.title == "Normal Work"
    assert (arxiv_item.status, arxiv_item.reason_code) == ("saved", "saved_new")
    assert arxiv_item.receipt.canonical_identity.key == "arxiv:2001.00001"
    assert arxiv_item.receipt.title == "A Preprint"
    for item in outcome.items:
        _assert_citable(service, item.receipt)
    entries = {entry.get("DOI") or entry.get("title"): entry for entry in _load_library(tmp_path / "references.json").items}
    assert set(entries) == {_NORMAL_DOI, "A Preprint"}


def test_alias_doi_saves_the_doi_org_primary_identity(tmp_path):
    service = _desktop_service(tmp_path)
    outcome = asyncio.run(service.save((
        WorkIntent("alias pick", identifiers=(WorkIdentifier("doi", _REQUESTED_ALIAS_DOI),)),
    )))

    item = outcome.items[0]
    assert item.status == "saved"
    # The identity is the DOI doi.org returns, not the requested alias.
    assert item.receipt.doi == _PRIMARY_DOI
    assert item.receipt.canonical_identity.key == _PRIMARY_DOI
    _assert_citable(service, item.receipt)
    [entry] = _load_library(tmp_path / "references.json").items
    assert entry["DOI"] == _PRIMARY_DOI
