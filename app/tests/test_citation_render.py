"""Renderer: first-appearance numbering and the neutral bibliography."""

from skills.citation.render import render_citations
from skills.citation.types import SourceRef


def _ref(source_id, **kwargs):
    defaults = dict(
        doi=f"10.1234/{source_id}",
        title=f"Title {source_id}",
        authors=["Ada Lovelace"],
        year=2021,
        venue="Venue",
        verification_level="doi_identity_verified",
    )
    defaults.update(kwargs)
    return SourceRef(source_id=source_id, **defaults)


REGISTRY = {
    "src-a": _ref("src-a"),
    "src-b": _ref("src-b", year=2020),
}


def _render(text):
    return render_citations(text, resolve=REGISTRY.get)


def test_numbers_assigned_by_first_appearance_and_reused():
    result = _render(
        "First [[cite:src-b]], then [[cite:src-a]], and again [[cite:src-b]]."
    )
    assert "First [1], then [2], and again [1]." in result
    assert "[1] Ada Lovelace. 2020. Title src-b." in result
    assert "[2] Ada Lovelace. 2021. Title src-a." in result


def test_retired_user_cite_marker_is_left_verbatim_not_numbered():
    # The gate blocks this form upstream; the renderer must not invent a
    # number for it even if it ever slipped through.
    result = _render("Per your link [[user-cite:usr-x]] and [[cite:src-a]].")
    assert "[[user-cite:usr-x]]" in result
    assert "[U1]" not in result
    assert "[1] Ada Lovelace. 2021. Title src-a." in result
    assert "[2]" not in result


def test_citation_needed_renders_placeholder_without_bibliography():
    result = _render("More research needed [[citation-needed]].")
    assert "More research needed [citation needed]." in result
    assert "Sources:" not in result


def test_bibliography_lists_cited_sources_in_order():
    result = _render("A [[cite:src-a]] B [[cite:src-b]]")
    assert result.rstrip().endswith(
        "Sources:\n"
        "[1] Ada Lovelace. 2021. Title src-a. Venue. DOI: 10.1234/src-a. "
        "[doi_identity_verified]\n"
        "[2] Ada Lovelace. 2020. Title src-b. Venue. DOI: 10.1234/src-b. "
        "[doi_identity_verified]"
    )


def test_bibliography_caps_authors_at_six_plus_et_al():
    ref = _ref("src-many", authors=[f"Author {i}" for i in range(1, 9)])
    entry = render_citations("[[cite:src-many]]", resolve={"src-many": ref}.get)
    assert "Author 6 et al." in entry
    assert "Author 7" not in entry


def test_bibliography_omits_missing_fields_never_guesses():
    ref = SourceRef(
        source_id="src-min", doi="10.1/x" + "yz", title="Only Title",
        verification_level="doi_identity_verified",
    )
    entry = render_citations("[[cite:src-min]]", resolve={"src-min": ref}.get)
    assert entry.rstrip().endswith("[1] Only Title. DOI: 10.1/xyz. [doi_identity_verified]")


def test_markers_inside_code_are_left_verbatim():
    text = "Use `[[cite:src-a]]` markers.\n```\n[[cite:src-b]]\n```\nReal [[cite:src-a]]."
    result = _render(text)
    assert "`[[cite:src-a]]`" in result
    assert "[[cite:src-b]]" in result
    assert "Real [1]." in result
    assert "Title src-b" not in result


def test_web_links_pass_through_unnumbered():
    result = _render("See [docs](https://example.org) and [[cite:src-a]].")
    assert "[docs](https://example.org)" in result
    assert "example.org. [" not in result.split("Sources:")[1].replace(
        "10.1234/src-a", ""
    )
