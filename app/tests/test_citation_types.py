import pytest

from skills.citation.types import (
    CanonicalIdentity, PublishedDateFilter, SourceRef,
    is_citable_source, source_id_for,
)


def test_date_filter_is_fail_closed():
    filt = PublishedDateFilter.from_year_range(2020, 2022)
    assert filt.admits_year(2021)
    assert not filt.admits_year(None)
    assert not filt.admits_year(2023)
    with pytest.raises(ValueError):
        PublishedDateFilter.from_year_range(2023, 2020)


def test_verification_shapes_require_a_matching_canonical_identity():
    doi = SourceRef(
        "src-b", "10.1234/b", "B",
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.1234/b"),
    )
    assert is_citable_source(doi)
    mismatched = SourceRef(
        "src-b", "10.1234/b", "B",
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.1234/other"),
    )
    assert not is_citable_source(mismatched)
    # Without a canonical identity nothing is citable.
    assert not is_citable_source(SourceRef("src-a", "10.1234/a", "A"))
    authority = SourceRef(
        "src-c", None, "C",
        verification_level="authority_metadata_verified",
        canonical_identity=CanonicalIdentity("arxiv", "2001.00001"),
    )
    assert is_citable_source(authority)
    authority_with_doi = SourceRef(
        "src-c", "10.1234/c", "C",
        verification_level="authority_metadata_verified",
        canonical_identity=CanonicalIdentity("arxiv", "2001.00001"),
    )
    assert not is_citable_source(authority_with_doi)


def test_source_ids_are_stable_hashes_of_the_canonical_identity():
    # Same values the retired bundle storage produced, so markers stay stable.
    assert source_id_for(CanonicalIdentity("doi", "10.1234/A")) == "src-1db13d16e66c"
    assert source_id_for(CanonicalIdentity("arxiv", "2001.00001")) == "src-9f84bd3dd456"
    assert source_id_for(CanonicalIdentity("doi", "10.1234/a")) == source_id_for(
        CanonicalIdentity("doi", "10.1234/A")
    )
