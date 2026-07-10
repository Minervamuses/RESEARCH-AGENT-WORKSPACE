"""Canonical BibTeX validation: 1-entry rule, preamble, cap, junk discard."""

import pytest

from skills.citation.bibtex_canonical import (
    MAX_BIBTEX_BYTES,
    BibtexValidationError,
    inject_doi,
    parse_canonical_bibtex,
)

GOOD = """@article{vaswani2017,
  title = {Attention Is All You Need},
  author = {Vaswani, Ashish and Shazeer, Noam},
  journal = {NeurIPS},
  year = {2017},
  doi = {10.48550/arXiv.1706.03762},
}
"""


def test_parses_single_entry_and_extracts_fields():
    result = parse_canonical_bibtex(GOOD)
    assert result.entry_key == "vaswani2017"
    assert result.entry_type == "article"
    assert result.title == "Attention Is All You Need"
    assert result.authors == ["Vaswani, Ashish", "Shazeer, Noam"]
    assert result.year == 2017
    assert result.doi == "10.48550/arXiv.1706.03762"
    assert result.venue == "NeurIPS"
    assert result.text.startswith("@article{vaswani2017")
    assert result.text.endswith("\n")


def test_comments_macros_and_surrounding_junk_are_discarded():
    noisy = (
        "response junk before\n"
        "@comment{ignore me}\n"
        '@string{jj = "Journal of Tests"}\n'
        "@article{k1,\n"
        "  title = {T},\n"
        "  journal = jj,\n"
        "  year = {2020},\n"
        "}\n"
        "junk after\n"
    )
    result = parse_canonical_bibtex(noisy)
    assert result.venue == "Journal of Tests"
    # Canonical serialization keeps only the entry, macro expanded.
    assert "@comment" not in result.text
    assert "@string" not in result.text
    assert "junk" not in result.text


def test_rejects_multiple_entries():
    two = GOOD + "\n@article{other,\n  title = {X},\n  year = {2020},\n}\n"
    with pytest.raises(BibtexValidationError) as exc:
        parse_canonical_bibtex(two)
    assert exc.value.code == "not_exactly_one_entry"


def test_rejects_nonempty_preamble():
    payload = '@preamble{"\\\\newcommand{\\\\x}{y}"}\n' + GOOD
    with pytest.raises(BibtexValidationError) as exc:
        parse_canonical_bibtex(payload)
    assert exc.value.code == "nonempty_preamble"


def test_rejects_oversized_payload():
    padding = "%" + "x" * MAX_BIBTEX_BYTES + "\n"
    with pytest.raises(BibtexValidationError) as exc:
        parse_canonical_bibtex(padding + GOOD)
    assert exc.value.code == "payload_too_large"


def test_rejects_malformed_and_empty_payloads():
    with pytest.raises(BibtexValidationError) as exc:
        parse_canonical_bibtex("@article{broken, title = {unterminated")
    assert exc.value.code == "parse_failed"
    with pytest.raises(BibtexValidationError):
        parse_canonical_bibtex("")
    with pytest.raises(BibtexValidationError):
        parse_canonical_bibtex("<html>404 not found</html>")


def test_latex_title_is_flattened_for_comparison():
    payload = (
        "@article{k,\n"
        "  title = {On {S}chr\\\"{o}dinger Operators},\n"
        "  year = {1999},\n"
        "}\n"
    )
    result = parse_canonical_bibtex(payload)
    assert result.title == "On Schrödinger Operators"


def test_inject_doi_adds_field_and_refuses_existing():
    no_doi = parse_canonical_bibtex(
        "@article{k,\n  title = {T},\n  year = {2020},\n}\n"
    )
    assert no_doi.doi is None
    injected = inject_doi(no_doi, "10.1234/abc")
    assert injected.doi == "10.1234/abc"
    assert "10.1234/abc" in injected.text
    # Round-trips as valid canonical BibTeX.
    assert parse_canonical_bibtex(injected.text).doi == "10.1234/abc"
    with pytest.raises(BibtexValidationError):
        inject_doi(injected, "10.9/other")


def test_year_extraction_is_tolerant_of_wrappers():
    result = parse_canonical_bibtex(
        "@article{k,\n  title = {T},\n  year = {c. 2020},\n}\n"
    )
    assert result.year == 2020
