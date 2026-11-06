"""bime-appendix17.csl against the English examples printed in Appendix 17 二.8."""

import json

import pytest

from skills.citation import csl_render
from skills.citation.csl_render import list_styles, render

pytestmark = pytest.mark.skipif(csl_render.find_pandoc() is None, reason="Pandoc is not installed")

ITEMS = [
    {"id": "anderson1998", "type": "article-journal",
     "title": "A new technique for rapid deployment of rollover protective structures",
     "author": [{"family": "Anderson", "given": "G. T."}, {"family": "Renard", "given": "C. V."},
                {"family": "Strein", "given": "L. M."}, {"family": "Cayo", "given": "E. C."},
                {"family": "Mervin", "given": "M. M."}],
     "issued": {"date-parts": [[1998]]}, "container-title": "Applied Engineering in Agriculture",
     "container-title-short": "Applied Eng. in Agric.", "volume": "23", "issue": "2", "page": "34–42"},
    {"id": "miller1980", "type": "paper-conference", "title": "Sorghum: A new fuel",
     "author": [{"family": "Miller", "given": "F. R."}, {"family": "Creelman", "given": "R. A."}],
     "issued": {"date-parts": [[1980]]},
     "container-title": "Proc. 35th Annual Corn and Sorghum Industry Research Conference", "page": "219-232",
     "editor": [{"family": "Londen", "given": "H. D."}, {"family": "Wilkinson", "given": "W."}],
     "publisher-place": "Washington, DC", "publisher": "Am. Seed Trade Assoc."},
    {"id": "nsc2000", "type": "webpage", "title": "Injury Facts Online",
     "author": [{"literal": "NSC"}], "issued": {"date-parts": [[2000]]},
     "publisher-place": "Itasca, Ill.", "publisher": "National Safety Council",
     "URL": "www.nsc.org", "accessed": {"date-parts": [[2000, 12, 17]]}},
    {"id": "sas1990", "type": "software", "title": "SAS User's Guide: Statistics",
     "author": [{"literal": "SAS"}], "issued": {"date-parts": [[1990]]}, "version": "6a",
     "publisher-place": "Cary, N.C.", "publisher": "SAS Institute, Inc."},
    {"id": "campbell1991", "type": "thesis",
     "title": "The lower limit of soil water potential for potato growth",
     "author": [{"family": "Campbell", "given": "M. D."}], "issued": {"date-parts": [[1991]]},
     "genre": "PhD dissertation", "publisher-place": "Pullman, Wash.",
     "publisher": "Washington State University, Department of Agricultural Engineering"},
    {"id": "smith1985a", "type": "article-journal", "title": "Alpha", "author": [{"family": "Smith", "given": "J."}],
     "issued": {"date-parts": [[1985]]}, "container-title": "J. X", "volume": "1", "page": "1-2"},
    {"id": "smith1985b", "type": "article-journal", "title": "Beta", "author": [{"family": "Smith", "given": "J."}],
     "issued": {"date-parts": [[1985]]}, "container-title": "J. X", "volume": "1", "page": "3-4"},
    {"id": "smith1968", "type": "article-journal", "title": "Gamma",
     "author": [{"family": "Smith", "given": "A."}, {"family": "Kline", "given": "B."}],
     "issued": {"date-parts": [[1968]]}, "container-title": "J. X", "volume": "1", "page": "5-6"},
]
TEXT = ("[@anderson1998] [@miller1980; @nsc2000] [@sas1990] [@campbell1991] "
        "[@smith1985a; @smith1985b] [@smith1968] @smith1968 wrote. Later [-@nsc2000].\n")


@pytest.fixture
def rendered(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(ITEMS, ensure_ascii=False), encoding="utf-8")
    return render(TEXT, path, "bime-appendix17")


def test_style_is_listed():
    assert {"id": "bime-appendix17", "name": "NTU BIME Appendix 17 (author-year)",
            "kind": "author-date", "origin": "custom"} in list_styles()


def test_in_text_citations_follow_rule_4(rendered):
    assert [c["text"] for c in rendered.citations] == [
        "(Anderson et al., 1998)",
        "(Miller and Creelman, 1980; NSC, 2000)",
        "(SAS, 1990)",
        "(Campbell, 1991)",
        "(Smith, 1985a; Smith, 1985b)",
        "(Smith and Kline, 1968)",
        "Smith and Kline (1968)",
        "(2000)",
    ]


def test_reference_entries_match_the_regulation_examples(rendered):
    entries = {e["key"]: e["text"] for e in rendered.bibliography}
    assert entries["anderson1998"] == (
        "Anderson, G. T., C. V. Renard, L. M. Strein, E. C. Cayo, and M. M. Mervin. 1998. "
        "A new technique for rapid deployment of rollover protective structures. "
        "Applied Eng. in Agric. 23(2): 34-42."
    )
    assert entries["miller1980"] == (
        "Miller, F. R., and R. A. Creelman. 1980. Sorghum: A new fuel. "
        "In “Proc. 35th Annual Corn and Sorghum Industry Research Conference”, 219-232. "
        "H. D. Londen and W. Wilkinson, eds. Washington, DC: Am. Seed Trade Assoc."
    )
    assert entries["nsc2000"] == (
        "NSC. 2000. Injury Facts Online. Itasca, Ill.: National Safety Council. "
        "Available at: www.nsc.org. Accessed 17 December 2000."
    )
    assert entries["sas1990"] == (
        "SAS. 1990. SAS User's Guide: Statistics. Ver. 6a. Cary, N.C.: SAS Institute, Inc."
    )
    assert entries["campbell1991"] == (
        "Campbell, M. D. 1991. The lower limit of soil water potential for potato growth. "
        "PhD dissertation. Pullman, Wash.: Washington State University, Department of Agricultural Engineering."
    )


def test_reference_order_is_alphabetical_then_year(rendered):
    assert [e["key"] for e in rendered.bibliography] == [
        "anderson1998", "campbell1991", "miller1980", "nsc2000", "sas1990",
        "smith1985a", "smith1985b", "smith1968",
    ]


CJK = [
    {"id": "tian1989", "type": "article-journal", "language": "zh-TW", "title": "檸檬顏色選別裝置之研製",
     "author": [{"family": "田", "given": "秉才"}, {"family": "陳", "given": "世銘"}, {"family": "馮", "given": "丁樹"}],
     "issued": {"date-parts": [[1989]]}, "container-title": "農業工程學報", "volume": "35", "issue": "4", "page": "73-82"},
    {"id": "zhang1992", "type": "article-journal", "language": "zh-TW", "title": "芋頭收穫機之研究",
     "author": [{"family": "張", "given": "福祥"}, {"family": "盧", "given": "福明"}],
     "issued": {"date-parts": [[1992]]}, "container-title": "農業機械學刊", "volume": "1", "issue": "1", "page": "50-59"},
    {"id": "doh2001", "type": "webpage", "language": "zh-TW", "title": "健康食品安全評估方法",
     "author": [{"literal": "行政院衛生署"}], "issued": {"date-parts": [[2001]]}, "publisher-place": "台北",
     "publisher": "行政院衛生署", "URL": "http://www.doh.gov.tw/", "accessed": {"date-parts": [[2001, 2, 12]]}},
    {"id": "yamada2000", "type": "article-journal", "language": "ja", "title": "果実選別装置の研究",
     "author": [{"family": "山田", "given": "太郎"}], "issued": {"date-parts": [[2000]]},
     "container-title": "農業機械学会誌", "volume": "62", "issue": "1", "page": "10-20"},
]


def test_chinese_branch_with_language_field(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(CJK + ITEMS[:1], ensure_ascii=False), encoding="utf-8")
    out = render("[@zhang1992] [@tian1989] [@doh2001] [@yamada2000] [@anderson1998]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == [
        "(張與盧，1992)",
        "(田 等人，1989)",  # known limit: the processor puts a space before the et-al term
        "(行政院衛生署，2001)", "(山田，2000)", "(Anderson et al., 1998)",
    ]
    entries = {e["key"]: e["text"] for e in out.bibliography}
    assert entries["tian1989"] == "田秉才、陳世銘、馮丁樹。1989。檸檬顏色選別裝置之研製。農業工程學報 35(4): 73-82。"
    assert entries["doh2001"] == (
        "行政院衛生署。2001。健康食品安全評估方法。台北：行政院衛生署。網址：http://www.doh.gov.tw/。上網日期：2001-02-12。"
    )
    order = [e["key"] for e in out.bibliography]
    # zh before ja before untagged English; stroke order is not expressible.
    assert order[-2:] == ["yamada2000", "anderson1998"]


SMITH_JONES = {
    "id": "smith2020", "type": "article-journal", "title": "Grain drying",
    "author": [{"family": "Smith", "given": "A."}, {"family": "Jones", "given": "B."}],
    "issued": {"date-parts": [[2020]]}, "container-title": "Trans. ASAE", "volume": "3", "page": "1-9",
}


@pytest.mark.parametrize("language", [None, "en", "en-US", "de", "fr-FR"])
def test_non_cjk_language_keeps_the_english_format(tmp_path, language):
    """Acceptance P2: "language": "en" must not switch to 與/，."""
    item = dict(SMITH_JONES, **({"language": language} if language else {}))
    path = tmp_path / "references.json"
    path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    out = render("[@smith2020]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == ["(Smith and Jones, 2020)"]
    assert out.bibliography[0]["text"] == "Smith, A., and B. Jones. 2020. Grain drying. Trans. ASAE 3: 1-9."
    assert path.read_bytes() == before


@pytest.mark.parametrize(("language", "expected"), [("zh-TW", "(張與盧，1992)"), ("zh", "(張與盧，1992)"),
                                                    ("chi", "(張與盧，1992)"), (None, "(張與盧，1992)")])
def test_chinese_entries_with_or_without_language(tmp_path, language, expected):
    item = {k: v for k, v in CJK[1].items() if k != "language"}
    if language:
        item["language"] = language
    path = tmp_path / "references.json"
    path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    out = render("[@zhang1992]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == [expected]
    assert out.bibliography[0]["text"] == "張福祥、盧福明。1992。芋頭收穫機之研究。農業機械學刊 1(1): 50-59。"


def test_japanese_is_inferred_from_kana_and_ordered_after_chinese(tmp_path):
    items = [{k: v for k, v in item.items() if k != "language"} for item in CJK] + [SMITH_JONES]
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out = render("[@yamada2000] [@smith2020] [@tian1989]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == ["(山田，2000)", "(Smith and Jones, 2020)", "(田 等人，1989)"]
    assert [e["key"] for e in out.bibliography][-2:] == ["yamada2000", "smith2020"]


APOSTROPHES = [
    {"id": "obrien2020", "type": "article-journal", "title": "Users' views of O'Brien's tool",
     "author": [{"family": "O'Brien", "given": "Pat"}, {"family": "D'Arcy", "given": "Mike"}],
     "issued": {"date-parts": [[2020]]}, "container-title": "J. X", "volume": "1", "page": "1-2",
     "URL": "https://example.org/it's"},
    {"id": "obama2020", "type": "article-journal", "title": "Typographic data: Users’ guide",
     "author": [{"family": "Obama", "given": "B."}], "issued": {"date-parts": [[2020]]},
     "container-title": "J. X", "volume": "1", "page": "3-4"},
    {"id": "obrist2020", "type": "article-journal", "title": "Third",
     "author": [{"family": "Obrist", "given": "C."}], "issued": {"date-parts": [[2020]]},
     "container-title": "J. X", "volume": "1", "page": "5-6"},
]


def _apostrophe_library(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(APOSTROPHES, ensure_ascii=False), encoding="utf-8")
    return path


def test_appendix17_keeps_straight_apostrophes_from_the_data(tmp_path):
    """User decision (2026-11-06): straight apostrophes, as in bime_word's output."""
    path = _apostrophe_library(tmp_path)
    before = path.read_bytes()
    out = render("[@obrien2020; @obama2020; @obrist2020]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == ["(O'Brien and D'Arcy, 2020; Obama, 2020; Obrist, 2020)"]
    entries = {e["key"]: e["text"] for e in out.bibliography}
    assert entries["obrien2020"] == (
        "O'Brien, P., and M. D'Arcy. 2020. Users' views of O'Brien's tool. J. X 1: 1-2."
    )
    assert entries["obama2020"] == "Obama, B. 2020. Typographic data: Users’ guide. J. X 1: 3-4."
    # Sorted as if the apostrophe were absent (bime_word folds punctuation away).
    assert [e["key"] for e in out.bibliography] == ["obama2020", "obrien2020", "obrist2020"]
    assert path.read_bytes() == before


def test_apostrophes_in_urls_are_untouched_and_other_styles_unchanged(tmp_path):
    from skills.citation.csl_render import protect_apostrophes

    copy, placeholder = protect_apostrophes(APOSTROPHES, "")
    assert placeholder is not None
    assert copy[0]["URL"] == "https://example.org/it's"
    assert "'" not in copy[0]["title"] and placeholder in copy[0]["title"]
    assert copy[0]["id"] == "obrien2020"
    apa = render("[@obrien2020]", _apostrophe_library(tmp_path), "apa")
    assert "O’Brien" in apa.citations[0]["text"]


def test_document_text_keeps_its_own_typography(tmp_path):
    from skills.citation.csl_render import export_markdown

    out = export_markdown("It's cited [@obrien2020].\n", _apostrophe_library(tmp_path), "bime-appendix17")
    assert out.startswith("It’s cited (O'Brien and D'Arcy, 2020).")
    assert "O'Brien, P., and M. D'Arcy. 2020. [Users' views of O'Brien's tool](https://example.org/it's)." in out


def test_no_free_placeholder_leaves_text_unchanged():
    from skills.citation.csl_render import _APOSTROPHE_PLACEHOLDERS, protect_apostrophes

    items = [{"id": "a", "title": "x'y"}]
    copy, placeholder = protect_apostrophes(items, "".join(_APOSTROPHE_PLACEHOLDERS))
    assert (copy, placeholder) == (items, None)


def _names(*families, given="A."):
    return [{"family": family, "given": given} for family in families]


NAME_CASES = [
    {"id": "yih2020", "type": "article-journal", "title": "One",
     "author": [{"family": "Yih", "given": "Wen-tau"}, {"family": "Godard", "given": "Jean-Luc"},
                {"family": "Lee", "given": "Hao-Ping (Hank)"}],
     "issued": {"date-parts": [[2020]]}, "container-title": "J. X", "volume": "1", "page": "1-2"},
    {"id": "trunc2024", "type": "article", "title": "Truncated in the source",
     "author": _names(*[f"F{i}" for i in range(1, 11)]) + [{"literal": "et al."}],
     "issued": {"date-parts": [[2024]]}, "number": "arXiv:2407.21783"},
    {"id": "twelve2024", "type": "article", "title": "Twelve real authors",
     "author": _names(*[f"G{i}" for i in range(1, 13)]), "issued": {"date-parts": [[2024]]}, "number": "arXiv:1"},
    {"id": "pair2023", "type": "article", "title": "Two then et al",
     "author": _names("Pa", "Pb") + [{"literal": "et al"}], "issued": {"date-parts": [[2023]]}, "number": "arXiv:2"},
    {"id": "wang2020", "type": "article-journal", "language": "zh-TW", "title": "水稻研究",
     "author": [{"family": "王", "given": "小明"}, {"family": "李", "given": "大華"}, {"literal": "等"}],
     "issued": {"date-parts": [[2020]]}, "container-title": "農業工程學報", "volume": "1", "page": "1-2"},
]


def test_given_names_follow_bime_word_rules(tmp_path):
    """User decision D11: Wen-tau -> W.-t. and no nickname, without editing the file."""
    path = tmp_path / "references.json"
    path.write_text(json.dumps(NAME_CASES, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    out = render("[@yih2020]", path, "bime-appendix17")
    assert out.bibliography[0]["text"] == "Yih, W.-t., J.-L. Godard, and H.-P. Lee. 2020. One. J. X 1: 1-2."
    assert path.read_bytes() == before


def test_truncated_author_lists_end_with_et_al(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(NAME_CASES, ensure_ascii=False), encoding="utf-8")
    out = render("[@trunc2024] [@twelve2024] [@pair2023] [@wang2020]", path, "bime-appendix17")
    assert [c["text"] for c in out.citations] == [
        "(F1 et al., 2024)", "(G1 et al., 2024)", "(Pa et al., 2023)", "(王 等人，2020)",
    ]
    entries = {e["key"]: e["text"] for e in out.bibliography}
    first_ten = "F1, A., " + ", ".join(f"A. F{i}" for i in range(2, 11))
    assert entries["trunc2024"] == f"{first_ten}, et al. 2024. Truncated in the source. arXiv:2407.21783."
    assert entries["twelve2024"].startswith("G1, A., A. G2, ") and ", A. G11, and A. G12. 2024." in entries["twelve2024"]
    assert entries["pair2023"] == "Pa, A., A. Pb, et al. 2023. Two then et al. arXiv:2."
    assert entries["wang2020"] == "王小明、李大華等。2020。水稻研究。農業工程學報 1: 1-2。"
    apa = render("[@trunc2024]", path, "apa")
    assert "et al." in apa.bibliography[0]["text"]  # other styles read the file as before


def test_preprocessing_never_leaks_the_flag_variable():
    from skills.citation.csl_render import TRUNCATION_FLAG, mark_truncated_author_lists

    items = [{"id": "a", "author": [{"family": "A"}], TRUNCATION_FLAG: "user data"}]
    assert mark_truncated_author_lists(items) == [{"id": "a", "author": [{"family": "A"}]}]



def _lang_item(key, family, language, title):
    item = {"id": key, "type": "article-journal", "title": title, "author": [{"family": family, "given": "一"}],
            "issued": {"date-parts": [[2000]]}, "container-title": "期刊", "volume": "1", "page": "1-2"}
    if language:
        item["language"] = language
    return item


@pytest.mark.parametrize(("zh", "ja"), [("zh", "ja"), ("chi", "jpn"), ("zho", "ja-JP"), ("zh-Hant", None)])
def test_language_code_spelling_does_not_change_the_order(tmp_path, zh, ja):
    """Acceptance 2026-11-06: chi/jpn put Japanese before Chinese."""
    items = [_lang_item("j1", "山田", ja, "日本語の研究"), _lang_item("z1", "張", zh, "中文研究"),
             dict(SMITH_JONES)]
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out = render("[@j1] [@z1] [@smith2020]", path, "bime-appendix17")
    assert [e["key"] for e in out.bibliography] == ["z1", "j1", "smith2020"]


def test_mixed_chinese_codes_sort_as_one_group(tmp_path):
    items = [_lang_item("zhTW", "張", "zh-TW", "甲"), _lang_item("zh", "李", "zh", "乙"),
             _lang_item("chi", "王", "chi", "丙"), _lang_item("none", "田", None, "丁"),
             _lang_item("ja", "山田", "ja-JP", "日本語の研究")]
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out = render(" ".join(f"[@{item['id']}]" for item in items), path, "bime-appendix17")
    order = [e["key"] for e in out.bibliography]
    assert order[-1] == "ja"
    # One Chinese group ordered by the collation of the surname, whatever the code.
    plain = [dict(item, language="zh") if item["id"] != "ja" else item for item in items]
    path.write_text(json.dumps(plain, ensure_ascii=False), encoding="utf-8")
    same = render(" ".join(f"[@{item['id']}]" for item in items), path, "bime-appendix17")
    assert order == [e["key"] for e in same.bibliography]
