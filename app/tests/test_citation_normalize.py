"""Title normalization contracts: NFKC, casefold, HTML, LaTeX, empty-title."""

from skills.citation.normalize import normalize_title, strip_latex


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
    assert normalize_title("Ａｔｔｅｎｔｉｏｎ") == normalize_title("attention")
    assert normalize_title("Tom &amp; Jerry") == normalize_title("Tom & Jerry")


def test_case_and_punctuation_insensitive_matching():
    assert normalize_title("Attention Is All You Need") == normalize_title(
        "attention is all you need"
    )
    assert normalize_title(
        "BERT: Pre-training of Deep Bidirectional Transformers"
    ) == normalize_title("BERT — Pre training of Deep Bidirectional Transformers")


def test_chinese_and_mixed_unicode_titles_match_exactly():
    assert normalize_title("注意力就是你所需要的") == normalize_title(
        "注意力就是你所需要的"
    )
    assert normalize_title("注意力就是你所需要的") != normalize_title(
        "注意力不是你所需要的"
    )
    assert normalize_title("大規模語言模型 (LLM) 綜述") == normalize_title(
        "大規模語言模型 LLM 綜述"
    )


def test_empty_titles_normalize_to_not_comparable():
    for title in ("", None, "{}", "..."):
        assert normalize_title(title) == ""
    assert normalize_title("real title") == "real title"


def test_latex_and_plain_versions_of_same_title_match():
    assert normalize_title(
        r"On the {C}omplexity of \emph{Schr\"{o}dinger} Operators"
    ) == normalize_title("On the Complexity of Schrödinger Operators")
