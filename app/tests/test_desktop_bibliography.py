"""Desktop bibliography.* methods: inspect, render, set_style, remove, add, export."""

import asyncio
import hashlib
import json
import uuid
import zipfile

import pytest

from agent.desktop.catalog import inspect_project
from agent.desktop.protocol import validate_result_data
from agent.desktop.service import DesktopServiceError
from skills.citation import csl_render
from skills.citation.hub import CitationProviderHub
from test_desktop_document_service import _setup, _Sink
from test_desktop_service import _open_test_project, _service
from tests.test_citation_doi_first_save import JOURNAL_DOI, PREPRINT_DOI, Fetcher

needs_pandoc = pytest.mark.skipif(csl_render.find_pandoc() is None, reason="Pandoc is not installed")

LIBRARY = [
    {"id": "ng2021journal", "type": "article-journal", "title": "A Journal Article",
     "author": [{"family": "Ng", "given": "Kim"}], "issued": {"date-parts": [[2021]]},
     "container-title": "Nature", "volume": "1", "page": "1-2", "DOI": JOURNAL_DOI},
    {"id": "lab2019site", "type": "webpage", "title": "Lab site",
     "author": [{"literal": "Plant Lab"}], "issued": {"date-parts": [[2019]]}, "URL": "https://example.org/"},
]
TEXT = "Claim [@ng2021journal; @ghost1999].\n"


def _write_library(root, items=LIBRARY):
    path = root / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


async def _project(tmp_path, *, text=TEXT, name="稿件.md"):
    service = _service(tmp_path)
    await _open_test_project(service, tmp_path)
    document = tmp_path / name
    document.write_text(text, encoding="utf-8")
    context = await service.dispatch("document.open", {"path": str(document)})
    return service, document, context


async def _call(service, method, params, sink=None):
    data = await service.dispatch(method, params, event_sink=sink)
    validate_result_data(method, data)
    return data


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_methods_require_an_open_project(tmp_path):
    async def run():
        service = _service(tmp_path)
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.inspect", {})
        assert excinfo.value.code == "SESSION_NOT_READY"
    asyncio.run(run())


def test_inspect_reports_library_document_and_styles(tmp_path):
    async def run():
        service, _document, context = await _project(tmp_path)
        empty = await _call(service, "bibliography.inspect", {})
        assert empty["libraryStatus"] == "missing" and empty["libraryFingerprint"] is None
        assert empty["styleId"] == "apa" and empty["styleConfigured"] is False
        assert {"apa", "ieee", "bime-appendix17"} <= {s["id"] for s in empty["styles"]}
        path = _write_library(tmp_path)
        data = await _call(service, "bibliography.inspect", {"documentContext": {**context, "sourceText": TEXT + "Unsaved @lab2019site.\n"}})
        assert data["libraryStatus"] == "ok" and data["libraryFingerprint"] == _sha(path)
        assert data["documentFormat"] == "markdown"
        assert data["order"] == ["ng2021journal", "ghost1999", "lab2019site"]
        assert data["missing"] == ["ghost1999"]
        assert data["uncited"] == []
        assert {e["key"]: e["citedCount"] for e in data["entries"]} == {"ng2021journal": 1, "lab2019site": 1}
        assert [u["known"] for u in data["uses"]] == [True, False, True]
        (tmp_path / "references.json").write_text("{bad", encoding="utf-8")
        broken = await _call(service, "bibliography.inspect", {})
        assert broken["libraryStatus"] == "error" and broken["libraryErrorCode"] == "library_malformed"
    asyncio.run(run())


@needs_pandoc
def test_render_markdown_and_refuse_latex(tmp_path):
    async def run():
        service, _document, context = await _project(tmp_path)
        _write_library(tmp_path)
        before = context["sourceText"]
        data = await _call(service, "bibliography.render", {"documentContext": context, "styleId": "ieee"})
        assert data["styleId"] == "ieee"
        assert data["citations"][0]["keys"] == ["ng2021journal", "ghost1999"]
        assert data["citations"][0]["start"] == 7
        assert [e["key"] for e in data["entries"]] == ["ng2021journal"]
        assert data["missing"] == ["ghost1999"]
        assert all(segment["entry"] == 0 for segment in data["segments"])
        apa = await _call(service, "bibliography.render", {"documentContext": context})
        assert apa["styleId"] == "apa" and apa["entries"][0]["text"] != data["entries"][0]["text"]
        assert context["sourceText"] == before
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.render", {"documentContext": context, "styleId": "nope"})
        assert excinfo.value.code == "PROTOCOL_INVALID"
        tex = tmp_path / "thesis.tex"
        tex.write_text("\\cite{ng2021journal}\n", encoding="utf-8")
        tex_context = await service.dispatch("document.open", {"path": str(tex)})
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.render", {"documentContext": tex_context})
        assert excinfo.value.code == "PROTOCOL_INVALID" and ".bib" in str(excinfo.value)
        tex_report = await _call(service, "bibliography.inspect", {"documentContext": tex_context})
        assert tex_report["documentFormat"] == "latex" and tex_report["order"] == ["ng2021journal"]
    asyncio.run(run())


def test_set_style_rewrites_only_the_metadata_value(tmp_path):
    async def run():
        service, _document, _context = await _project(tmp_path)
        research = tmp_path / "RESEARCH.md"
        before = inspect_project(str(tmp_path), tmp_path / "store")
        data = await _call(service, "bibliography.set_style", {"styleId": "bime-appendix17"})
        after = inspect_project(str(tmp_path), tmp_path / "store")
        assert data == {"styleId": "bime-appendix17", "researchFingerprint": after["researchFingerprint"]}
        assert after["researchFingerprint"] != before["researchFingerprint"]
        assert (after["rulesText"], after["rulesFingerprint"]) == (before["rulesText"], before["rulesFingerprint"])
        assert service._project["researchFingerprint"] == after["researchFingerprint"]
        text = research.read_text(encoding="utf-8")
        assert '"citationStyle":"bime-appendix17"' in text
        assert (await _call(service, "bibliography.inspect", {}))["styleConfigured"] is True
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.set_style", {"styleId": "nope"})
        assert excinfo.value.code == "PROTOCOL_INVALID"
        service._turn_active = True
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.set_style", {"styleId": "apa"})
        assert excinfo.value.code == "BUSY_TURN"
        service._turn_active = False
        assert research.read_text(encoding="utf-8") == text
    asyncio.run(run())


def test_a_turn_still_submits_after_set_style(tmp_path, monkeypatch):
    async def run():
        service, model, _path, context = await _setup(tmp_path, monkeypatch)
        await _call(service, "bibliography.set_style", {"styleId": "ieee"})
        sink = _Sink(service, context)
        result = await service.dispatch("session.turn", {
            "text": "分析這份稿件", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context,
        }, event_sink=sink)
        assert result["text"] == "分析完成，沒有修改稿件。"
    asyncio.run(run())


def test_remove_checks_the_fingerprint(tmp_path):
    async def run():
        service, _document, _context = await _project(tmp_path)
        path = _write_library(tmp_path)
        stale = "0" * 64
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.remove", {"key": "lab2019site", "libraryFingerprint": stale})
        assert excinfo.value.code == "BIBLIOGRAPHY_CONFLICT"
        before = path.read_bytes()
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.remove", {"key": "nope", "libraryFingerprint": _sha(path)})
        assert excinfo.value.code == "PROTOCOL_INVALID"
        assert path.read_bytes() == before
        data = await _call(service, "bibliography.remove", {"key": "lab2019site", "libraryFingerprint": _sha(path)})
        assert data == {"key": "lab2019site", "libraryFingerprint": _sha(path)}
        assert json.loads(path.read_text(encoding="utf-8")) == LIBRARY[:1]
    asyncio.run(run())


class _DenySink:
    request_id = str(uuid.uuid4())

    def __init__(self, service, approve):
        self.service, self.approve, self.events, self.tasks = service, approve, [], []

    def __call__(self, event, data):
        self.events.append((event, data))
        if event == "approval.required":
            self.tasks.append(asyncio.create_task(self.service.dispatch("approval.resolve", {
                "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                "turnId": data["turnId"], "approved": self.approve,
            })))


def test_add_uses_citation_save_approval_and_merges(tmp_path, monkeypatch):
    hub = CitationProviderHub(env={}, fetcher=Fetcher())
    monkeypatch.setattr("skills.citation.hub.get_provider_hub", lambda: hub)

    async def run():
        service, _document, _context = await _project(tmp_path)
        library = tmp_path / "references.json"
        deny = _DenySink(service, False)
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.add", {"identifier": PREPRINT_DOI}, event_sink=deny)
        await asyncio.gather(*deny.tasks)
        assert excinfo.value.code == "APPROVAL_DENIED"
        approval = next(data for event, data in deny.events if event == "approval.required")
        assert approval["operation"] == "citation.save" and str(library) in approval["description"]
        assert not library.exists() and not (tmp_path / "cite").exists()

        allow = _DenySink(service, True)
        data = await _call(service, "bibliography.add", {"identifier": f"https://doi.org/{PREPRINT_DOI}"}, allow)
        await asyncio.gather(*allow.tasks)
        assert data == {"status": "added", "key": "lee2020biorxiv", "reasonCode": None, "libraryFingerprint": _sha(library)}
        assert list((tmp_path / "cite").glob("*/reference.bib"))

        service._bash_permission_mode = "bypass"
        again = await _call(service, "bibliography.add", {"identifier": PREPRINT_DOI})
        assert (again["status"], again["key"]) == ("existing", "lee2020biorxiv")
        missing = await _call(service, "bibliography.add", {"identifier": "10.9999/does-not-exist"})
        assert missing["status"] == "failed" and missing["key"] is None and missing["reasonCode"]
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.add", {"identifier": "not an id"})
        assert excinfo.value.code == "PROTOCOL_INVALID"
    asyncio.run(run())


@needs_pandoc
def test_export_writes_beside_the_document_and_keeps_the_source(tmp_path):
    async def run():
        service, document, context = await _project(tmp_path)
        _write_library(tmp_path)
        source = _sha(document)
        docx = await _call(service, "bibliography.export", {"documentContext": context, "format": "docx", "styleId": "apa"})
        assert docx["path"] == str(document.parent / "稿件.apa.docx")
        with zipfile.ZipFile(docx["path"]) as archive:
            assert "Ng, 2021" in archive.read("word/document.xml").decode("utf-8")
        markdown = await _call(service, "bibliography.export", {"documentContext": context, "format": "markdown"})
        assert markdown["path"] == str(document.parent / "稿件.apa.md")
        assert "[@" not in (tmp_path / "稿件.apa.md").read_text(encoding="utf-8")
        bib = await _call(service, "bibliography.export", {"format": "bib"})
        assert bib["path"] == str(tmp_path / "references.bib")
        assert "@article{ng2021journal" in (tmp_path / "references.bib").read_text(encoding="utf-8")
        assert _sha(document) == source
        tex = tmp_path / "thesis.tex"
        tex.write_text("\\cite{ng2021journal}\n", encoding="utf-8")
        tex_context = await service.dispatch("document.open", {"path": str(tex)})
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", {"documentContext": tex_context, "format": "docx"})
        assert excinfo.value.code == "PROTOCOL_INVALID"
        tex_bib = await _call(service, "bibliography.export", {"documentContext": tex_context, "format": "bib"})
        assert tex_bib["path"] == str(tmp_path / "references.bib")
    asyncio.run(run())


def test_bibliography_failures_are_typed(tmp_path, monkeypatch):
    async def run():
        service, _document, context = await _project(tmp_path)
        (tmp_path / "references.json").write_text("{bad", encoding="utf-8")
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", {"format": "bib"})
        assert excinfo.value.code == "BIBLIOGRAPHY_FAILED"
        _write_library(tmp_path)
        monkeypatch.setattr(csl_render, "find_pandoc", lambda: None)
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.render", {"documentContext": context})
        assert excinfo.value.code == "BIBLIOGRAPHY_FAILED" and "Pandoc" in str(excinfo.value)
    asyncio.run(run())


def test_update_project_metadata_keeps_everything_else(tmp_path, monkeypatch):
    from agent.desktop import catalog

    research = tmp_path / "RESEARCH.md"
    head = "# 研究\n\n規則：引用要有來源。\n\n<!-- research-agent-project\n"
    tail = "\n-->\n\n## 附註\n尾段 🙂\n"
    research.write_text(head + json.dumps(
        {"version": 1, "historyDirectory": "h", "bibliography": "refs/a.json"}, indent=2) + tail, encoding="utf-8")
    _meta, rules_before = catalog._metadata_and_rules(research.read_bytes())
    fingerprint = catalog.update_project_metadata(tmp_path, {"citationStyle": "ieee"})
    text = research.read_text(encoding="utf-8")
    assert text.startswith(head) and text.endswith(tail)
    payload = json.loads(text[len(head):-len(tail)])
    assert list(payload) == ["version", "historyDirectory", "bibliography", "citationStyle"]
    assert payload["citationStyle"] == "ieee"
    assert catalog._metadata_and_rules(research.read_bytes())[1] == rules_before
    assert fingerprint == hashlib.sha256(research.read_bytes()).hexdigest()
    with pytest.raises(catalog.CatalogMalformedError):
        catalog.update_project_metadata(tmp_path, {"historyDirectory": "elsewhere"})

    real = catalog._research_bytes
    calls = []

    def changed_on_second_read(path):
        calls.append(path)
        data = real(path)
        return data + b"x" if len(calls) == 2 else data

    monkeypatch.setattr(catalog, "_research_bytes", changed_on_second_read)
    before = research.read_bytes()
    with pytest.raises(catalog.CatalogConflictError):
        catalog.update_project_metadata(tmp_path, {"citationStyle": "apa"})
    assert research.read_bytes() == before
    assert not list(tmp_path.glob(".RESEARCH.md.*"))
