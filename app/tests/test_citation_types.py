"""Contracts for the citation workflow core types."""

import pytest

from skills.citation.types import (
    PERSIST_SCHEMA_VERSION,
    CitationCandidate,
    CitationResult,
    ProviderState,
    SourceRef,
    VerificationCheck,
    VerificationReport,
)


def test_failed_result_must_not_carry_accepted_doi():
    for status in (
        "cancelled",
        "no_doi",
        "provider_failed",
        "verification_failed",
        "storage_failed",
        "invalid_state",
    ):
        result = CitationResult(status=status)
        assert result.accepted_doi is None
        with pytest.raises(ValueError):
            CitationResult(status=status, accepted_doi="10.1/x")


def test_confirmed_result_requires_accepted_doi():
    with pytest.raises(ValueError):
        CitationResult(status="confirmed")
    result = CitationResult(status="confirmed", accepted_doi="10.1/x")
    assert result.accepted_doi == "10.1/x"


def test_source_ref_round_trips_through_dict():
    ref = SourceRef(
        source_id="src-1",
        doi="10.1234/abc",
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        year=2017,
        venue="NeurIPS",
        work_type="proceedings-article",
        verification_level="identity_verified",
        provenance="doi.org-csl",
        bundle_path="/tmp/bundle",
    )
    data = ref.to_dict()
    assert data["schema_version"] == PERSIST_SCHEMA_VERSION
    restored = SourceRef.from_dict(data)
    assert restored == ref


def test_source_ref_from_dict_treats_missing_fields_as_empty():
    restored = SourceRef.from_dict({"source_id": "src-2", "title": "T"})
    assert restored.doi is None
    assert restored.authors == []
    assert restored.year is None
    assert restored.venue == ""
    assert restored.bundle_path is None
    # Unknown/absent verification level never silently upgrades.
    assert restored.verification_level == "user_supplied_unverified"


def test_source_ref_rejects_unknown_verification_level_on_rehydrate():
    restored = SourceRef.from_dict(
        {"source_id": "s", "title": "t", "verification_level": "totally_verified"}
    )
    assert restored.verification_level == "user_supplied_unverified"


def test_verification_report_round_trip_and_passed():
    report = VerificationReport(
        checks=[
            VerificationCheck(name="doi_match", passed=True),
            VerificationCheck(name="bibtex_doi_match", passed=False, detail="mismatch"),
        ],
        warnings=["title conflict"],
        codes=["doi_injected_from_verified_lookup"],
    )
    assert report.passed is False
    restored = VerificationReport.from_dict(report.to_dict())
    assert restored == report
    assert VerificationReport(checks=[VerificationCheck("x", True)]).passed is True


def test_provider_state_round_trip():
    state = ProviderState(provider="crossref", status="rate_limited", detail="429")
    assert ProviderState.from_dict(state.to_dict()) == state


def test_candidate_label_formats_authors_and_year():
    cand = CitationCandidate(
        candidate_id="c1",
        workflow_id="w1",
        title="A Paper",
        authors=["First Author", "Second Author"],
        year=2020,
    )
    assert cand.short_label() == "A Paper (First Author et al., 2020)"
    untitled = CitationCandidate(candidate_id="c2", workflow_id="w1")
    assert untitled.short_label() == "(untitled)"


def test_published_date_filter_within_years_uses_utc_today():
    from datetime import date

    from skills.citation.types import PublishedDateFilter

    filt = PublishedDateFilter.within_years(5, today=date(2026, 7, 10))
    assert (filt.date_from, filt.date_to) == ("2021-07-10", "2026-07-10")
    assert (filt.year_from, filt.year_to) == (2021, 2026)
    # Feb 29 minus N years lands on Feb 28, never raises.
    leap = PublishedDateFilter.within_years(1, today=date(2024, 2, 29))
    assert leap.date_from == "2023-02-28"


def test_published_date_filter_year_range_and_fail_closed_admission():
    import pytest

    from skills.citation.types import PublishedDateFilter

    filt = PublishedDateFilter.from_year_range(2020, 2022)
    assert (filt.date_from, filt.date_to) == ("2020-01-01", "2022-12-31")
    assert filt.admits_year(2020) and filt.admits_year(2022)
    assert not filt.admits_year(2019) and not filt.admits_year(2023)
    assert not filt.admits_year(None)  # unknown year never qualifies

    open_ended = PublishedDateFilter.from_year_range(2021, None)
    assert open_ended.admits_year(2030)
    assert not open_ended.admits_year(2020)

    with pytest.raises(ValueError):
        PublishedDateFilter.from_year_range(None, None)
    with pytest.raises(ValueError):
        PublishedDateFilter.from_year_range(2022, 2020)
    with pytest.raises(ValueError):
        PublishedDateFilter.within_years(0)
