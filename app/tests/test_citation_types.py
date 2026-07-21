from datetime import date

import pytest

from skills.citation.types import (
    CanonicalIdentity, ProviderState, PublishedDateFilter, SourceRef,
    is_citable_source, source_identity,
)


def test_provider_state_round_trip():
    state = ProviderState("crossref", "rate_limited", "429")
    assert ProviderState.from_dict(state.to_dict()) == state


def test_date_filter_is_fail_closed():
    filt = PublishedDateFilter.from_year_range(2020, 2022)
    assert filt.admits_year(2021)
    assert not filt.admits_year(None)
    assert not filt.admits_year(2023)
    with pytest.raises(ValueError):
        PublishedDateFilter.from_year_range(2023, 2020)


def test_relative_date_filter_handles_bounds():
    filt = PublishedDateFilter.within_years(5, today=date(2026, 7, 13))
    assert (filt.year_from, filt.year_to) == (2021, 2026)


def test_source_identity_and_verification_shapes():
    legacy = SourceRef("src-a", "10.1234/a", "A")
    assert source_identity(legacy) == CanonicalIdentity("doi", "10.1234/a")
    assert is_citable_source(legacy)
    current = SourceRef("src-b", "10.1234/b", "B", schema_version=2, verification_level="doi_identity_verified", canonical_identity=CanonicalIdentity("doi", "10.1234/b"))
    assert is_citable_source(current)
    bad = SourceRef("src-b", "10.1234/b", "B", schema_version=2, verification_level="doi_identity_verified", canonical_identity=CanonicalIdentity("doi", "10.1234/other"))
    assert not is_citable_source(bad)


def test_source_ref_model_and_persistence_have_no_bundle_path():
    ref = SourceRef(
        "src-b",
        "10.1234/b",
        "B",
        schema_version=2,
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.1234/b"),
    )

    persisted = ref.to_persisted_dict()

    assert not hasattr(ref, "bundle_path")
    assert "bundle_path" not in persisted
    assert persisted["canonical_identity"] == {"kind": "doi", "value": "10.1234/b"}
