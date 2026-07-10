"""Title normalization contracts: NFKC, casefold, HTML, LaTeX, empty-title."""

from citation.normalize import normalize_title, strip_latex, titles_match


def test_latex_accents_and_glyphs_flatten_to_unicode():
    assert strip_latex(r"Schr\"{o}dinger") == "Schrödinger"
    assert strip_latex(r"G\'{e}rard and \ss{} and \o{}") == "Gérard and ß and ø"
    assert strip_latex(r"\'e") == "é"


def test_latex_commands_and_braces_are_dropped_keeping_content():
    assert (
        normalize_title(r"\emph{Attention} {I}s {A}ll {Y}ou \textbf{Need}")
        == "attention is all you need"
    )
    assert normalize_title(r"cost is 100\% \& rising") == "cost is 100 rising"


def test_html_entities_and_nfkc_fold_before_comparison():
    # Fullwidth letters NFKC-fold to ASCII for title comparison (unlike DOIs).
    assert titles_match("Ａｔｔｅｎｔｉｏｎ", "attention")
    assert titles_match("Tom &amp; Jerry", "Tom & Jerry")


def test_case_and_punctuation_insensitive_matching():
    assert titles_match(
        "Attention Is All You Need",
        "attention is all you need",
    )
    assert titles_match(
        "BERT: Pre-training of Deep Bidirectional Transformers",
        "BERT — Pre training of Deep Bidirectional Transformers",
    )


def test_chinese_and_mixed_unicode_titles_match_exactly():
    assert titles_match("注意力就是你所需要的", "注意力就是你所需要的")
    assert not titles_match("注意力就是你所需要的", "注意力不是你所需要的")
    assert titles_match("大規模語言模型 (LLM) 綜述", "大規模語言模型 LLM 綜述")


def test_empty_normalized_title_never_matches():
    assert not titles_match("", "")
    assert not titles_match(None, None)
    assert not titles_match("{}", "{}")
    assert not titles_match("...", "...")
    assert not titles_match("", "real title")


def test_latex_and_plain_versions_of_same_title_match():
    assert titles_match(
        r"On the {C}omplexity of \emph{Schr\"{o}dinger} Operators",
        "On the Complexity of Schrödinger Operators",
    )
