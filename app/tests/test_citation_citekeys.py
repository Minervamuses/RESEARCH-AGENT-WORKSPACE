"""Citation key parsing for Markdown (Pandoc syntax) and LaTeX."""

import pytest

from skills.citation.citekeys import find_citations, format_for_path, keys_in


@pytest.mark.parametrize(("text", "keys"), [
    ("[@a]", ["a"]),
    ("[@a; @b]", ["a", "b"]),
    ("[see @a, p. 33; also @b, ch. 2]", ["a", "b"]),
    ("[-@a]", ["a"]),
    ("as @a says", ["a"]),
    ("@a [p. 3] adds", ["a"]),
    ("@{a.b}x", ["a.b"]),
    ("@{with space}", []),
    ("end @key.", ["key"]),
    ("@key:sub. next", ["key:sub"]),
    ("@a_b-c:d#e$f%g&h+i?j<k>l~m/n", ["a_b-c:d#e$f%g&h+i?j<k>l~m/n"]),
    ("@_under @1digit @-neg", ["_under", "1digit"]),
    ("mail jane@doe.com", []),
    ("\\@escaped", []),
    ("`@code` and ``@x `y` @z``", []),
    ("```\n@fenced\n```\n~~~\n@tilde\n~~~\n", []),
    ("para\n\n    @indented\n", []),
    ("- item\n    @continued\n", ["continued"]),
    ("<!-- @c\n@d -->", []),
    ("$x @m$ and $$@mm$$", []),
    ("<https://x.com/@user> https://x.com/@bare <a@b.org>", ["bare"]),
    ("見@wang2020 見 @wang2021（@wang2022）。", ["wang2021", "wang2022"]),
    ("@王2020 研究", ["王2020"]),
    ("(@ex) at line start\n\nmid (@ex2) text", ["ex2"]),
    ("---\ntitle: \"@meta\"\n---\n\nBody @body", ["body"]),
    ("A[^1] then @after.\n\n[^1]: Note @fn.\n\n[^u]: Unused @unused.\n", ["fn", "after"]),
    # Link destinations, titles, reference targets, attributes and HTML tags
    # are never citations; link text and HTML element content are.
    ("[Profile](https://example.org/@ghost)", []),
    ('[Profile](https://example.org/@ghost "title @t1")', []),
    ("[Profile](https://example.org/x 'title @t2')", []),
    ("[Profile](<https://example.org/a b/@g3>)", []),
    ("[x]( https://x.org/@g16 )", []),
    ("[x](https://x.org/(p)/@g9) and @after", ["after"]),
    ("[see @a](https://x.org/@g4)", ["a"]),
    ("[@a](https://x.org/@g5)", ["a"]),
    ('![alt](pic/@g7.png "cap @g8")', []),
    ('[ref]: https://x.org/@g10 "t @g11"', []),
    ("[@k]: https://x.org", ["k"]),
    ('[x][r] and @real2\n\n[r]: https://x.org/@g19 "t @g21"\n', ["real2"]),
    ('[x](https://x.org/@g17){.cls key="@g20"}', []),
    ("[span @s1]{.cls}", ["s1"]),
    ('<a href="https://x.org/@g12">@inhtml</a>', ["inhtml"]),
    ('<span title="@g13">x</span>', []),
    ("[unclosed](https://x.org/@g14", ["g14"]),
    ("text](https://x.org/@g15)", ["g15"]),
    ("See @a<b>c and <em>@d</em>.", ["a<b>c", "d"]),
    # Footnotes and citation-shaped labels are not reference definitions.
    ("Claim[^n].\n\n[^n]: [@ghost]\n", ["ghost"]),
    ("Claim[^n].\n\n[^n]: https://x.org/@g1\n", ["g1"]),
    ("Claim[^n].\n\n[^n]: [x](https://x.org/@g2)\n", []),
    ("Claim[^n].\n\n[^n]: <https://x.org/@g6>\n", []),
    ("[@k]: https://x.org/@g3\n", ["k", "g3"]),
    ("[-@k]: https://x.org\n", ["k"]),
    ("[foo@bar]: https://x.org/@g4\n\n[x][foo@bar]\n", []),
])
def test_markdown_keys_match_pandoc_rules(text, keys):
    assert keys_in(text, "markdown") == keys


def test_markdown_groups_and_lines():
    uses = find_citations("x [@a; @b] y\nz @c [@d]", "markdown")
    assert [(u.key, u.line) for u in uses] == [("a", 1), ("b", 1), ("c", 2), ("d", 2)]
    assert uses[0].group == uses[1].group
    assert len({uses[1].group, uses[2].group, uses[3].group}) == 3


def test_positions_are_utf16_offsets():
    text = "😀 中 @a and 𝒳@x 𝒳 @b"
    uses = find_citations(text, "markdown")
    assert [u.key for u in uses] == ["a", "b"]
    encoded = text.encode("utf-16-le")
    for use in uses:
        token = encoded[use.start * 2:use.end * 2].decode("utf-16-le")
        assert token == "@" + use.key


def test_braced_key_span_covers_braces():
    use = find_citations("see @{a.b}.", "markdown")[0]
    assert (use.key, use.start, use.end) == ("a.b", 4, 10)


@pytest.mark.parametrize(("text", "keys"), [
    ("\\cite{a}", ["a"]),
    ("\\citep[see][p. 3]{a, b}", ["a", "b"]),
    ("\\citet*{a}", ["a"]),
    ("\\parencite[p. 2]{a}\\textcite{b}\\autocite{c}", ["a", "b", "c"]),
    ("\\nocite{a}\\nocite{*}", ["a"]),
    ("% \\cite{commented}\n\\cite{live}", ["live"]),
    ("50\\% \\cite{after_escaped_percent}", ["after_escaped_percent"]),
    ("\\begin{verbatim}\\cite{v}\\end{verbatim}\\cite{w}", ["w"]),
    ("\\citeauthor{a} \\citeyear{b}", ["a", "b"]),
    ("\\citation{notacite} \\cites", []),
    ("中文\\cite{王2020}。", ["王2020"]),
])
def test_latex_keys(text, keys):
    assert keys_in(text, "latex") == keys


def test_latex_positions_point_at_each_key():
    text = "😀 \\cite{a, bb}"
    uses = find_citations(text, "latex")
    encoded = text.encode("utf-16-le")
    assert [encoded[u.start * 2:u.end * 2].decode("utf-16-le") for u in uses] == ["a", "bb"]
    assert uses[0].group == uses[1].group


def test_format_for_path():
    assert format_for_path("x/thesis.MD") == "markdown"
    assert format_for_path("a.markdown") == "markdown"
    assert format_for_path("a.tex") == "latex"
    assert format_for_path("a.txt") is None
