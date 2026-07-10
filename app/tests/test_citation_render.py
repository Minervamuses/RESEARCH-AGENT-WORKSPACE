"""Renderer: first-appearance numbering, [U1] user sources, neutral bib."""

from skills.citation.render import format_bibliography_entry, render_citations
from skills.citation.types import SourceRef


def _ref(source_id, **kwargs):
    defaults = dict(
        doi=f"10.1234/{source_id}",
        title=f"Title {source_id}",
        authors=["Ada Lovelace"],
        year=2021,
        venue="Venue",
        verification_level="identity_verified",
    )
    defaults.update(kwargs)
    return SourceRef(source_id=source_id, **defaults)


REGISTRY = {
    "src-a": _ref("src-a"),
    "src-b": _ref("src-b", year=2020),
    "usr-x": _ref(
        "usr-x", doi=None, title="", authors=[], year=None, venue="",
        url="https://example.org/x",
        verification_level="user_supplied_unverified",
    ),
}


def _render(text):
    return render_citations(text, resolve=REGISTRY.get)


def test_numbers_assigned_by_first_appearance_and_reused():
    result = _render(
        "First [[cite:src-b]], then [[cite:src-a]], and again [[cite:src-b]]."
    )
    assert "First [1], then [2], and again [1]." in result.text
    assert [r.source_id for r in result.cited_sources] == ["src-b", "src-a"]


def test_user_sources_use_separate_u_sequence():
    result = _render("Per your link [[user-cite:usr-x]] and [[cite:src-a]].")
    assert "Per your link [U1] and [1]." in result.text
    assert [r.source_id for r in result.user_sources] == ["usr-x"]
    assert "[U1] https://example.org/x. [user_supplied_unverified]" in result.text


def test_citation_needed_renders_placeholder_without_bibliography():
    result = _render("More research needed [[citation-needed]].")
    assert "More research needed [citation needed]." in result.text
    assert "Sources:" not in result.text
    assert result.cited_sources == []


def test_bibliography_lists_cited_sources_in_order():
    result = _render("A [[cite:src-a]] B [[cite:src-b]]")
    assert result.text.rstrip().endswith(
        "Sources:\n"
        "[1] Ada Lovelace. 2021. Title src-a. Venue. DOI: 10.1234/src-a. "
        "[identity_verified]\n"
        "[2] Ada Lovelace. 2020. Title src-b. Venue. DOI: 10.1234/src-b. "
        "[identity_verified]"
    )


def test_bibliography_caps_authors_at_six_plus_et_al():
    ref = _ref("src-many", authors=[f"Author {i}" for i in range(1, 9)])
    entry = format_bibliography_entry(ref)
    assert "Author 6 et al." in entry
    assert "Author 7" not in entry


def test_bibliography_omits_missing_fields_never_guesses():
    ref = SourceRef(
        source_id="src-min", doi="10.1/x" + "yz", title="Only Title",
        verification_level="identity_verified",
    )
    entry = format_bibliography_entry(ref)
    assert entry == "Only Title. DOI: 10.1/xyz. [identity_verified]"


def test_markers_inside_code_are_left_verbatim():
    text = "Use `[[cite:src-a]]` markers.\n```\n[[cite:src-b]]\n```\nReal [[cite:src-a]]."
    result = _render(text)
    assert "`[[cite:src-a]]`" in result.text
    assert "[[cite:src-b]]" in result.text
    assert "Real [1]." in result.text
    assert [r.source_id for r in result.cited_sources] == ["src-a"]


def test_web_links_pass_through_unnumbered():
    result = _render("See [docs](https://example.org) and [[cite:src-a]].")
    assert "[docs](https://example.org)" in result.text
    assert "example.org. [" not in result.text.split("Sources:")[1].replace(
        "10.1234/src-a", ""
    )
