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
        "SAS. 1990. SAS User’s Guide: Statistics. Ver. 6a. Cary, N.C.: SAS Institute, Inc."
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
