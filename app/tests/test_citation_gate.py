"""Citation gate: masking, marker validation, and strict blocking."""

from skills.citation.gate import (
    GateViolation,
    build_safe_message,
    check_citations,
    mask_unscanned_regions,
)

VERIFIED = frozenset({"src-abc123"})


def _codes(violations: list[GateViolation]) -> set[str]:
    return {v.code for v in violations}


def _check(text, *, user_input="", verified=VERIFIED):
    return check_citations(
        text,
        verified_source_ids=verified,
        user_input=user_input,
    )


def test_clean_text_with_known_markers_passes():
    text = (
        "Transformers changed NLP [[cite:src-abc123]]. "
        "More work is needed [[citation-needed]]."
    )
    assert _check(text) == []


def test_dangling_and_unknown_markers_block():
    assert _codes(_check("x [[cite:src-nope]]")) == {"dangling_cite"}
    # The retired user-cite marker form is now just an unknown marker.
    assert _codes(_check("x [[user-cite:usr-nope]]")) == {"unknown_marker"}
    assert _codes(_check("x [[made-up:thing]]")) == {"unknown_marker"}


def test_raw_doi_blocks_even_inside_markdown_links():
    assert "raw_doi" in _codes(_check("see 10.1234/abc for details"))
    assert "raw_doi" in _codes(_check("see https://doi.org/10.1234/abc"))
    assert "raw_doi" in _codes(
        _check("see [the paper](https://doi.org/10.1234/abc)")
    )


def test_plain_web_links_are_allowed():
    assert _check("see [project page](https://example.org/model) for code") == []
    assert _check("docs at https://example.org/guide") == []


def test_raw_numeric_citation_blocks_but_link_labels_do_not():
    assert "raw_numeric_citation" in _codes(_check("as shown in [1]"))
    assert "raw_numeric_citation" in _codes(_check("evidence [12] suggests"))
    # A markdown link whose label is numeric is a link, not a citation.
    assert _check("see [1](https://example.org/one)") == []


def test_raw_author_year_blocks():
    assert "raw_author_year" in _codes(_check("as (Vaswani et al., 2017) showed"))
    assert "raw_author_year" in _codes(_check("Smith et al. (2020) argue that"))
    assert "raw_author_year" in _codes(_check("this idea (Smith, 2020) is old"))


def test_handwritten_bibliography_blocks():
    text = "Some answer.\n\n## References\n- Vaswani, A. Attention is all you need."
    assert "handwritten_bibliography" in _codes(_check(text))
    assert "handwritten_bibliography" in _codes(_check("答案。\n\n參考文獻:\n- 某論文"))


def test_code_fences_and_inline_code_are_not_scanned():
    text = (
        "Run this:\n```python\ndoi = '10.1234/abc'  # [1] (Smith, 2020)\n```\n"
        "and read `cite [2] 10.5555/xyz` carefully."
    )
    assert _check(text) == []


def test_user_quote_block_is_not_scanned_when_it_matches_input():
    user_input = "我看到論文說 as shown in [1] (Vaswani et al., 2017) 是對的嗎?"
    text = (
        "你引用的段落:\n"
        "> as shown in [1] (Vaswani et al., 2017)\n"
        "這段的說法需要查證 [[citation-needed]]。"
    )
    assert _check(text, user_input=user_input) == []


def test_quote_not_from_user_input_is_still_scanned():
    text = "> as shown in [1] (Vaswani et al., 2017)\nsounds right."
    codes = _codes(_check(text, user_input="unrelated question"))
    assert "raw_numeric_citation" in codes
    assert "raw_author_year" in codes


def test_mask_preserves_offsets():
    text = "abc ```x``` def"
    masked = mask_unscanned_regions(text)
    assert len(masked) == len(text)
    assert masked.startswith("abc ") and masked.endswith(" def")


def test_multiple_violations_all_reported():
    text = "as [1] and (Smith, 2020) plus [[cite:ghost]] and 10.1234/raw"
    codes = _codes(_check(text))
    assert codes == {
        "raw_numeric_citation",
        "raw_author_year",
        "dangling_cite",
        "raw_doi",
    }


def test_safe_message_lists_validation_errors():
    violations = _check("bad [1]")
    message = build_safe_message(violations)
    assert "raw_numeric_citation" in message
    assert "封鎖" in message
    assert "/citation" in message
