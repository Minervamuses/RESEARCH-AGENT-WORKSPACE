import pytest

from skills.citation.providers.base import (
    BibliographicQuery,
    ProviderRecord,
    QueryPass,
    plausible_identity_hit,
)


def test_bibliographic_query_is_normalized_immutable_and_secret_free():
    query = BibliographicQuery(
        "  Attention Is All You Need  ",
        authors=(" Ashish Vaswani ", ""),
        year=2017,
        venue=" NeurIPS ",
        work_type=" conference paper ",
    )

    assert query.title == "Attention Is All You Need"
    assert query.authors == ("Ashish Vaswani",)
    assert query.first_author == "Ashish Vaswani"
    assert query.fingerprint == (
        "Attention Is All You Need",
        ("Ashish Vaswani",),
        2017,
        "NeurIPS",
        "conference paper",
    )
    with pytest.raises(Exception):
        query.title = "changed"


def test_bibliographic_query_rejects_invalid_year_and_control_characters():
    with pytest.raises(ValueError, match="year"):
        BibliographicQuery("A Work", year=999)
    with pytest.raises(ValueError, match="control"):
        BibliographicQuery("A\x00Work")


def test_query_pass_preserves_provider_parameter_order():
    plan = QueryPass.build("strict", {"query.title": "A Work", "rows": "20"})
    assert plan.params == (("query.title", "A Work"), ("rows", "20"))
    assert plan.as_params() == {"query.title": "A Work", "rows": "20"}


def test_plausibility_check_is_loose_but_rejects_wrong_identity():
    query = BibliographicQuery(
        "Attention Is All You Need", authors=("Ashish Vaswani",), year=2017
    )
    matching = ProviderRecord(
        "fixture",
        "fixture:matching",
        0,
        title="Attention is all you need",
        authors=["Vaswani, Ashish"],
        year=2018,
    )
    wrong_title = ProviderRecord(
        "fixture",
        "fixture:wrong-title",
        0,
        title="A Survey of Transformer Models",
        authors=["Ashish Vaswani"],
        year=2017,
    )
    wrong_author = ProviderRecord(
        "fixture",
        "fixture:wrong-author",
        0,
        title="Attention Is All You Need",
        authors=["Someone Else"],
        year=2017,
    )

    assert plausible_identity_hit(query, matching)
    assert not plausible_identity_hit(query, wrong_title)
    assert not plausible_identity_hit(query, wrong_author)


def test_missing_provider_year_does_not_force_a_fallback():
    query = BibliographicQuery("A Work", authors=("Ada Author",), year=2020)
    record = ProviderRecord(
        "fixture", "fixture:1", 0, title="A Work", authors=["Ada Author"]
    )
    assert plausible_identity_hit(query, record)
