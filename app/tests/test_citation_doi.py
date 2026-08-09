"""DOI canonicalizer contracts: prefix stripping, single decode, no NFKC."""

from skills.citation.doi import (
    ascii_casefold,
    canonicalize_doi,
    doi_equal,
)


def test_canonicalize_strips_label_and_resolver_prefixes():
    for raw in (
        "10.1234/AbC.5",
        "doi:10.1234/AbC.5",
        "DOI: 10.1234/AbC.5",
        "https://doi.org/10.1234/AbC.5",
        "http://dx.doi.org/10.1234/AbC.5",
        "doi.org/10.1234/AbC.5",
        "https://www.doi.org/10.1234/AbC.5",
    ):
        assert canonicalize_doi(raw) == "10.1234/abc.5"


def test_canonicalize_html_unescape_and_percent_decode_exactly_once():
    # &amp; decodes once to &; %26 decodes once to &.
    assert canonicalize_doi("10.1000/a&amp;b") == "10.1000/a&b"
    assert canonicalize_doi("10.1000/a%26b") == "10.1000/a&b"
    # A DOI that legitimately contains a percent-encoded percent sign must
    # survive exactly one decode: %2526 -> %26, NOT &.
    assert canonicalize_doi("10.1000/a%2526b") == "10.1000/a%26b"


def test_canonicalize_is_ascii_only_case_folding_no_nfkc():
    # ASCII letters fold; non-ASCII characters are preserved verbatim.
    assert canonicalize_doi("10.1000/ＡＢＣ") == "10.1000/ＡＢＣ"  # fullwidth kept
    assert canonicalize_doi("10.1000/Ünïcode") == "10.1000/Ünïcode"
    assert ascii_casefold("AbCé") == "abcé"


def test_canonicalize_keeps_possibly_legal_trailing_punctuation():
    # A DOI suffix may legally end with ')' or '.'; canonicalization must not
    # blindly strip it.
    assert canonicalize_doi("10.1000/123(45)") == "10.1000/123(45)"
    assert canonicalize_doi("10.1000/abc.") == "10.1000/abc."


def test_canonicalize_rejects_non_doi_shapes():
    assert canonicalize_doi(None) is None
    assert canonicalize_doi("") is None
    assert canonicalize_doi("not a doi") is None
    assert canonicalize_doi("11.1234/x") is None
    assert canonicalize_doi("10.12/short-prefix") is None
    assert canonicalize_doi("10.1234/") is None


def test_doi_equal_compares_canonical_forms():
    assert doi_equal("DOI:10.1234/AbC", "https://doi.org/10.1234/abc")
    assert not doi_equal("10.1234/abc", "10.1234/abd")
    assert not doi_equal(None, "10.1234/abc")
    assert not doi_equal("junk", "junk")
