"""Citation gate: registry-backed marker integrity, not prose-style policing."""

from skills.citation.gate import (
    GateViolation,
    build_safe_message,
    check_citations,
    mask_unscanned_regions,
)

VERIFIED = frozenset({"src-abc123"})


def _codes(violations: list[GateViolation]) -> set[str]:
    return {violation.code for violation in violations}


def _check(text, *, user_input="", verified=VERIFIED, active=True):
    return check_citations(
        text,
        verified_source_ids=verified,
        citation_active=active,
        user_input=user_input,
    )


def test_known_markers_and_placeholder_pass_in_citation_mode():
    text = (
        "Transformers changed NLP [[cite:src-abc123]]. "
        "More work is needed [[citation-needed]]."
    )
    assert _check(text) == []


def test_dangling_and_unknown_markers_still_block():
    assert _codes(_check("x [[cite:src-nope]]")) == {"dangling_cite"}
    assert _codes(_check("x [[user-cite:usr-nope]]")) == {"unknown_marker"}
    assert _codes(_check("x [[made-up:thing]]")) == {"unknown_marker"}


def test_raw_doi_numeric_author_year_and_bibliography_are_allowed():
    text = (
        "See https://doi.org/10.1234/abc and [1]. "
        "As Smith et al. (2020) explain:\n\n"
        "## References\n- Smith, A. (2020). A paper."
    )
    assert _check(text) == []


def test_raw_citation_prose_is_also_allowed_outside_citation_mode():
    text = (
        "Evidence [12] and (Vaswani et al., 2017). "
        "DOI 10.48550/arXiv.1706.03762.\n\n"
        "參考文獻：\n- Vaswani et al."
    )
    assert _check(text, active=False) == []


def test_plain_web_links_are_allowed():
    assert _check("see [project page](https://example.org/model) for code") == []
    assert _check("docs at https://example.org/guide") == []


def test_code_fences_and_inline_code_are_not_scanned_for_markers():
    text = (
        "Run this:\n```python\nmarker = '[[cite:ghost]]'\n```\n"
        "and read `[[made-up:thing]]` carefully."
    )
    assert _check(text) == []


def test_user_quote_block_does_not_exempt_renderer_markers():
    user_input = "Why did it emit [[cite:ghost]]?"
    text = (
        "You wrote:\n"
        "> Why did it emit [[cite:ghost]]?\n"
        "That marker would otherwise be invalid."
    )
    assert _codes(_check(text, user_input=user_input)) == {"dangling_cite"}


def test_quote_not_from_user_input_is_still_scanned():
    codes = _codes(_check(
        "> Unsupported [[cite:ghost]].\nThat is wrong.",
        user_input="unrelated question",
    ))
    assert codes == {"dangling_cite"}


def test_mask_preserves_offsets():
    text = "abc ```[[cite:ghost]]``` def"
    masked = mask_unscanned_regions(text)
    assert len(masked) == len(text)
    assert masked.startswith("abc ") and masked.endswith(" def")


def test_multiple_marker_violations_are_all_reported():
    codes = _codes(_check(
        "[[cite:ghost]] plus [[made-up:thing]] and [[cite:another]]"
    ))
    assert codes == {"dangling_cite", "unknown_marker"}


def test_inactive_policy_blocks_every_renderer_marker_form():
    for text in (
        "ok [[cite:src-abc123]]",
        "todo [[citation-needed]]",
        "legacy [[user-cite:usr-x]]",
        "odd [[made-up]]",
    ):
        assert _codes(_check(text, active=False)) == {"citation_inactive_marker"}


def test_safe_message_describes_marker_errors_per_mode():
    message = build_safe_message(
        _check("bad [[cite:ghost]]"), citation_active=True,
    )
    assert "dangling_cite" in message
    assert "registry" in message
    assert "[[cite:" in message

    inactive = build_safe_message(
        _check("bad [[citation-needed]]", active=False),
        citation_active=False,
    )
    assert "citation_inactive_marker" in inactive
    assert "/citation" in inactive
