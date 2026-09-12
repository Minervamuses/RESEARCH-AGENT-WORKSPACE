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


@pytest.mark.parametrize("variation", ["original", "reversed", "rank_provider", "score"])
def test_earliest_year_tie_cannot_be_resolved_by_nontemporal_ranking(variation):
    intent = WorkIntent("earliest", title="A Work", version_kind="earliest")
    records = [manifestation("published"), manifestation("preprint", rank=1)]
    if variation == "reversed":
        records.reverse()
    elif variation == "rank_provider":
        records[0].rank, records[1].rank = 1, 0
        records[0].provider, records[1].provider = "z", "a"
    elif variation == "score":
        records[0].title = "A Works"
    evaluated = [evaluate_record(intent, record) for record in records]
    assert all(decision.status == "eligible" for decision in evaluated)
    if variation == "score":
        assert evaluated[0].evidence.score < evaluated[1].evidence.score

    decision = decide_resolution(intent, records)

    assert decision.status == "ambiguous"
    assert decision.reason_code == "earliest_year_tie"
    assert decision.record is None
    assert {record.doi for record in decision.alternatives} == {
        "10.1000/published", "10.1000/preprint",
    }


@pytest.mark.parametrize("count", [1, 2])
def test_earliest_without_any_year_is_ambiguous_even_for_one_identity(count):
    records = [manifestation(version, year=None) for version in ("published", "preprint")][:count]

    decision = decide_resolution(
        WorkIntent("earliest", title="A Work", version_kind="earliest"), records,
    )

    assert decision.status == "ambiguous"
    assert decision.reason_code == "earliest_year_missing"
    assert decision.record is None
    assert decision.alternatives == tuple(records)


def test_earliest_deduplicates_canonical_doi_before_comparing_years():
    earliest = manifestation("preprint")
    duplicate = manifestation("preprint", doi="https://doi.org/10.1000/PREPRINT")
    duplicate.provider = "other"

    decision = decide_resolution(
        WorkIntent("earliest", title="A Work", version_kind="earliest"),
        [earliest, duplicate, manifestation("published", year=2022)],
    )

    assert decision.status == "eligible"
    assert decision.record is earliest


@pytest.mark.parametrize("other_years", [(2022, 2022), (None,)])
def test_earliest_unique_known_minimum_survives_later_ties_and_unknown_years(other_years):
    earliest = manifestation("preprint")
    others = [
        manifestation("published", year=year, doi=f"10.1000/other-{index}")
        for index, year in enumerate(other_years)
    ]

    decision = decide_resolution(
        WorkIntent("earliest", title="A Work", version_kind="earliest"),
        [*others, earliest],
    )

    assert decision.status == "eligible"
    assert decision.record is earliest


@pytest.mark.parametrize("year,reason", [(2020, "earliest_year_tie"), (None, "earliest_year_missing")])
def test_earliest_alternatives_only_include_eligible_minimum_identities_and_cap_at_five(year, reason):
    records = [manifestation("preprint", year=year, doi=f"10.1000/{i}") for i in range(6)]
    excluded = manifestation("published", year=2019)
    excluded.title = "An unrelated work"

    decision = decide_resolution(
        WorkIntent("earliest", title="A Work", version_kind="earliest"),
        [excluded, *records, records[0], manifestation("published", year=2022)]
        if year is not None else [excluded, *records, records[0]],
    )

    assert decision.status == "ambiguous"
    assert decision.reason_code == reason
    assert decision.record is None
    assert len(decision.alternatives) == 5
    assert len({record.doi for record in decision.alternatives}) == 5
    assert all(record in records for record in decision.alternatives)


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
