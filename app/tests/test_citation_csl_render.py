"""Pandoc-backed rendering and export of Markdown citations."""

import hashlib
import io
import json
import struct
import zipfile
import zlib

import pytest

from skills.citation import csl_render
from skills.citation.csl_render import RenderError, export_docx, export_markdown, export_target, list_styles, render

pytestmark = pytest.mark.skipif(csl_render.find_pandoc() is None, reason="Pandoc is not installed")

ITEMS = [
    {"id": "smith2020deep", "type": "article-journal", "title": "Deep learning for crops",
     "author": [{"family": "Smith", "given": "Jane"}], "issued": {"date-parts": [[2020]]},
     "container-title": "Journal of Agri", "volume": "12", "page": "1-10", "DOI": "10.1000/abc"},
    {"id": "adams2019robot", "type": "paper-conference", "title": "Robot harvesting",
     "author": [{"family": "Adams", "given": "Min"}, {"family": "Chen", "given": "Wei"}],
     "issued": {"date-parts": [[2019]]}, "container-title": "Proc. ICRA"},
    {"id": "zhou2021field", "type": "report", "title": "Field notes",
     "author": [{"literal": "Zhou Lab"}], "issued": {"date-parts": [[2021]]}, "publisher": "Zhou Lab"},
]
TEXT = "😀 First [@zhou2021field]. Then [@smith2020deep; @adams2019robot, p. 3].\n\nAgain @smith2020deep.\n"


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(ITEMS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def test_styles_are_listed():
    ids = [style["id"] for style in list_styles()]
    assert {"apa", "modern-language-association", "ieee", "chicago-author-date"} <= set(ids)


def test_switching_style_changes_output_but_not_the_source(library):
    text_hash = hashlib.sha256(TEXT.encode()).hexdigest()
    library_bytes = library.read_bytes()
    apa = render(TEXT, library, "apa")
    ieee = render(TEXT, library, "ieee")
    assert [c["text"] for c in apa.citations] != [c["text"] for c in ieee.citations]
    assert [e["text"] for e in apa.bibliography] != [e["text"] for e in ieee.bibliography]
    assert hashlib.sha256(TEXT.encode()).hexdigest() == text_hash
    assert library.read_bytes() == library_bytes
    assert [c["text"] for c in apa.citations] == [
        "(Zhou Lab, 2021)", "(Adams & Chen, 2019, p. 3; Smith, 2020)", "Smith (2020)",
    ]
    assert [c["text"] for c in ieee.citations] == ["[1]", "[2], [3, p. 3]", "[2]"]


def test_bibliography_order_follows_the_style(library):
    assert [e["key"] for e in render(TEXT, library, "ieee").bibliography] == [
        "zhou2021field", "smith2020deep", "adams2019robot",
    ]
    assert [e["key"] for e in render(TEXT, library, "apa").bibliography] == [
        "adams2019robot", "smith2020deep", "zhou2021field",
    ]


def test_citations_map_to_utf16_source_positions(library):
    rendered = render(TEXT, library, "apa")
    encoded = TEXT.encode("utf-16-le")
    spans = [encoded[c["start"] * 2:c["end"] * 2].decode("utf-16-le") for c in rendered.citations]
    assert spans == ["@zhou2021field", "@smith2020deep; @adams2019robot", "@smith2020deep"]
    assert rendered.citations[1]["keys"] == ["smith2020deep", "adams2019robot"]


def test_segments_carry_italics_and_links(library):
    entry = next(e for e in render(TEXT, library, "apa").bibliography if e["key"] == "smith2020deep")
    assert {"text": "Journal of Agri", "italic": True} in [
        {k: v for k, v in s.items()} for s in entry["segments"] if s.get("italic") and "Journal" in s["text"]
    ]
    assert any(s.get("url") == "https://doi.org/10.1000/abc" for s in entry["segments"])


def test_missing_keys_are_reported_not_fatal(library):
    rendered = render("See [@smith2020deep; @ghost1999].", library, "apa")
    assert rendered.missing == ["ghost1999"]
    assert len(rendered.citations) == 1
    assert [e["key"] for e in rendered.bibliography] == ["smith2020deep"]


def test_missing_library_file_renders_with_all_keys_missing(tmp_path):
    rendered = render("See [@a].", tmp_path / "references.json", "apa")
    assert rendered.missing == ["a"]
    assert rendered.bibliography == []


def test_docx_export_contains_rendered_citations(library):
    data = export_docx(TEXT, library, "apa")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "Zhou Lab, 2021" in xml
    assert "Journal of Agri" in xml
    assert "@smith2020deep" not in xml


def _png(path):
    raw = b"\x00\xff\x00\x00"
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


def test_docx_never_fetches_remote_images_but_embeds_local_ones(library, tmp_path, monkeypatch):
    _png(tmp_path / "figure.png")
    text = "![remote](https://example.invalid/img.png)\n\n![local](figure.png)\n\n[@smith2020deep]\n"
    sent = []
    real_run = csl_render._run

    def spy(args, stdin, *, timeout):
        sent.append((args, stdin))
        return real_run(args, stdin, timeout=timeout)

    monkeypatch.setattr(csl_render, "_run", spy)
    data = export_docx(text, library, "apa", resource_dir=tmp_path)
    writer_args, writer_input = sent[-1]
    assert "--sandbox" not in writer_args and "--resource-path" in writer_args
    assert "https://example.invalid/img.png" in writer_input.decode()
    assert '"t": "Image", "c": [["", [], []], [{"t": "Str", "c": "remote"}]' not in writer_input.decode()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
        xml = archive.read("word/document.xml").decode("utf-8")
    assert len(media) == 1  # only the local figure
    assert "remote" in xml
    sandboxed = export_docx(text, library, "apa")
    with zipfile.ZipFile(io.BytesIO(sandboxed)) as archive:
        assert not [n for n in archive.namelist() if n.startswith("word/media/")]


def test_markdown_export_has_no_citation_syntax(library):
    out = export_markdown(TEXT, library, "ieee")
    assert "[@" not in out and "@smith2020deep" not in out
    assert "\\[1\\]" in out and "“Deep learning for crops,”" in out
    assert ":::" not in out and "{.csl" not in out and "<div" not in out


def test_export_targets_sit_beside_the_document_and_exclude_bibtex(tmp_path):
    document = tmp_path / "稿件.md"
    assert export_target("docx", document_path=document, style_id="apa") == tmp_path / "稿件.apa.docx"
    assert export_target("markdown", document_path=document, style_id="ieee") == tmp_path / "稿件.ieee.md"
    assert set(csl_render.EXPORT_SUFFIXES) == {"docx", "markdown"}
    assert not hasattr(csl_render, "export_bib")
    with pytest.raises(KeyError):
        export_target("bib", document_path=document, style_id="apa")


def test_missing_pandoc_is_a_clear_error(library, monkeypatch):
    monkeypatch.setattr(csl_render, "find_pandoc", lambda: None)
    with pytest.raises(RenderError) as excinfo:
        render(TEXT, library, "apa")
    assert excinfo.value.code == "pandoc_unavailable"


def test_unknown_style_and_bad_library(library, tmp_path):
    with pytest.raises(RenderError) as excinfo:
        render(TEXT, library, "nope")
    assert excinfo.value.code == "style_unknown"
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(RenderError) as excinfo:
        render(TEXT, bad, "apa")
    assert excinfo.value.code == "library_malformed"


def test_cjk_language_rule():
    from skills.citation.csl_render import cjk_language

    assert cjk_language({"language": "en", "title": "水稻"}) is None  # explicit language wins
    assert cjk_language({"language": "zh-Hant"}) == "zh"
    assert cjk_language({"language": "jpn"}) == "ja"
    assert cjk_language({"language": "zhx"}) is None
    assert cjk_language({"title": "果実選別装置の研究"}) == "ja"
    assert cjk_language({"author": [{"family": "王", "given": "小明"}], "title": "Rice"}) == "zh"
    assert cjk_language({"title": "Rice drying"}) is None


def test_only_language_branch_styles_get_a_normalized_copy(library, monkeypatch):
    items = json.loads(library.read_text(encoding="utf-8"))
    items[0]["language"] = "en"
    library.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    before = library.read_bytes()
    seen = []
    real_run = csl_render._run

    def spy(args, stdin, *, timeout):
        if "--bibliography" in args:
            path = args[args.index("--bibliography") + 1]
            seen.append((path, json.loads(open(path, encoding="utf-8").read())))
        return real_run(args, stdin, timeout=timeout)

    monkeypatch.setattr(csl_render, "_run", spy)
    render(TEXT, library, "apa")
    render(TEXT, library, "bime-appendix17")
    assert seen[0][0] == str(library) and seen[0][1][0]["language"] == "en"
    assert seen[1][0] != str(library) and "language" not in seen[1][1][0]
    assert library.read_bytes() == before
