"""Model-selected citation targets and deterministic bibliographic lookup."""

import pytest

from skills.citation.providers.base import ProviderRecord
from skills.citation.resolution import (
    WorkIdentifier,
    WorkIntent,
    decide_resolution,
    evaluate_record,
)


def manifestation(version, *, rank=0, year=2020, doi=None):
    return ProviderRecord(
        "fixture",
        f"fixture:{version}",
        rank,
        title="A Work",
        authors=["Ada Author"],
        year=year,
        venue="A Venue" if version == "published" else "",
        work_type="article" if version == "published" else version,
        version_kind=version,
        doi=doi or f"10.1000/{version}",
    )


@pytest.mark.parametrize("requested", ["published", "preprint", "repository", "repost"])
def test_model_selected_version_directly_filters_manifestations(requested):
    other = "published" if requested != "published" else "preprint"
    intent = WorkIntent("selected", title="A Work", version_kind=requested)

    decision = decide_resolution(intent, [
        manifestation(other, rank=0),
        manifestation(requested, rank=1),
    ])

    assert decision.status == "eligible"
    assert decision.reason_code == "best_match"
    assert decision.record.version_kind == requested


def test_missing_version_uses_best_deterministic_match_without_forced_clarification():
    intent = WorkIntent("this paper", title="A Work", authors=("Ada Author",))

    decision = decide_resolution(intent, [
        manifestation("published", rank=0),
        manifestation("preprint", rank=1),
    ])

    assert decision.status == "eligible"
    assert decision.record.version_kind == "published"
    assert decision.reason_code != "version_clarification_required"


def test_earliest_selection_chooses_oldest_dated_manifestation():
    intent = WorkIntent("earliest", title="A Work", version_kind="earliest")

    decision = decide_resolution(intent, [
        manifestation("published", year=2022, rank=0),
        manifestation("preprint", year=2020, rank=1),
    ])

    assert decision.status == "eligible"
    assert decision.record.year == 2020
    assert decision.record.version_kind == "preprint"


@pytest.mark.parametrize("derivative_type", ["review", "posted-content"])
def test_model_selected_original_research_excludes_derivative_record(
    derivative_type,
):
    intent = WorkIntent(
        "original",
        title="A Work",
        work_kind="original_research",
    )
    review = manifestation("published")
    review.work_type = derivative_type

    decision = evaluate_record(intent, review)

    assert decision.status == "not_found"
    assert decision.reason_code == "not_original_research"


@pytest.mark.parametrize(
    ("intent", "record", "reason"),
    [
        (
            WorkIntent("title", title="Right work"),
            ProviderRecord("x", "x:1", 0, title="Entirely different"),
            "title_mismatch",
        ),
        (
            WorkIntent("author", title="A Work", authors=("Ada Author",)),
            ProviderRecord("x", "x:1", 0, title="A Work", authors=["Other Person"]),
            "author_mismatch",
        ),
        (
            WorkIntent("year", title="A Work", year=2017),
            ProviderRecord("x", "x:1", 0, title="A Work", year=2020),
            "year_mismatch",
        ),
        (
            WorkIntent("venue", title="A Work", venue="Venue A"),
            ProviderRecord("x", "x:1", 0, title="A Work", venue="Venue B"),
            "venue_mismatch",
        ),
    ],
)
def test_descriptive_fields_still_reject_nonmatching_provider_records(
    intent, record, reason,
):
    decision = evaluate_record(intent, record)
    assert decision.status == "not_found"
    assert decision.reason_code == reason


def test_exact_identifier_is_the_model_selected_target_not_a_second_semantic_vote():
    intent = WorkIntent(
        "selected DOI",
        title="A stale conversational title",
        identifiers=(WorkIdentifier("doi", "10.1000/abc"),),
    )
    record = ProviderRecord(
        "doi.org",
        "doi.org:10.1000/abc",
        0,
        title="Authoritative title",
        doi="10.1000/abc",
    )

    decision = evaluate_record(intent, record)

    assert decision.status == "eligible"
    assert decision.reason_code == "exact_identifier"


def test_conflicting_identifier_does_not_match_a_different_record():
    intent = WorkIntent(
        "selected DOI",
        identifiers=(WorkIdentifier("doi", "10.1000/right"),),
    )
    record = ProviderRecord(
        "x", "x:wrong", 0, title="A Work", doi="10.1000/wrong",
    )

    decision = evaluate_record(intent, record)

    assert decision.status == "not_found"
    assert decision.reason_code == "identifier_mismatch"


def test_bounds_and_identifier_validation_remain_strict():
    with pytest.raises(ValueError):
        WorkIntent("x", title="a" * 513)
    with pytest.raises(ValueError):
        WorkIdentifier("doi", "c1")
    with pytest.raises(ValueError):
        WorkIntent("x", identifiers=tuple(
            WorkIdentifier("doi", f"10.1000/{index}") for index in range(9)
        ))
