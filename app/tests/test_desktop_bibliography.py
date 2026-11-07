"""Desktop bibliography.* methods: inspect, render, set_style, remove, add, export."""

import asyncio
import hashlib
import json
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

import pytest

from agent.desktop import bime_export
from agent.desktop.catalog import inspect_project
from agent.desktop.protocol import ProtocolError, validate_message, validate_result_data
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
        assert excinfo.value.code == "PROTOCOL_INVALID" and "Markdown documents" in str(excinfo.value)
        assert ".bib" not in str(excinfo.value)
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
        assert _sha(document) == source
        tex = tmp_path / "thesis.tex"
        tex.write_text("\\cite{ng2021journal}\n", encoding="utf-8")
        tex_context = await service.dispatch("document.open", {"path": str(tex)})
        for fmt in ("docx", "markdown"):
            with pytest.raises(DesktopServiceError) as excinfo:
                await service.dispatch("bibliography.export", {"documentContext": tex_context, "format": fmt})
            assert excinfo.value.code == "PROTOCOL_INVALID"
    asyncio.run(run())


def test_bibtex_export_is_rejected_without_writing(tmp_path):
    async def run():
        service, _document, context = await _project(tmp_path)
        _write_library(tmp_path)
        tex = tmp_path / "thesis.tex"
        tex.write_text("\\cite{ng2021journal}\n", encoding="utf-8")
        tex_context = await service.dispatch("document.open", {"path": str(tex)})
        before = sorted(path.name for path in tmp_path.iterdir())
        for params in ({"format": "bib"}, {"documentContext": context, "format": "bib"},
                       {"documentContext": tex_context, "format": "bib"}):
            with pytest.raises(DesktopServiceError) as excinfo:
                await service.dispatch("bibliography.export", params)
            assert excinfo.value.code == "PROTOCOL_INVALID"
        assert sorted(path.name for path in tmp_path.iterdir()) == before
        assert not list(tmp_path.rglob("*.bib"))
        with pytest.raises(ProtocolError) as raised:
            validate_message({"protocolVersion": 1, "messageType": "request", "requestId": str(uuid.uuid4()),
                              "method": "bibliography.export", "params": {"documentContext": context, "format": "bib"}})
        assert raised.value.code == "PROTOCOL_INVALID"
        with pytest.raises(ProtocolError):
            validate_result_data("bibliography.export", {"format": "bib", "path": str(tmp_path / "references.bib")})
        validate_result_data("bibliography.export", {"format": "markdown", "path": str(tmp_path / "稿件.apa.md")})
    asyncio.run(run())


CITED = "Claim [@ng2021journal].\n"


def _bime_params(context):
    return {"documentContext": context, "format": "bime_docx"}


@needs_pandoc
def test_bime_export_writes_the_docx_and_reports_beside_the_saved_file(tmp_path):
    async def run():
        service, document, context = await _project(tmp_path, text=CITED)
        _write_library(tmp_path)
        source = _sha(document)
        data = await _call(service, "bibliography.export", {**_bime_params(context), "styleId": "ieee"})
        assert data["format"] == "bime_docx" and data["path"] == str(tmp_path / "稿件.bime.docx")
        for suffix in (".bime.docx", ".bime.audit.json", ".bime.audit.md", ".bime.bime.json"):
            assert (tmp_path / f"稿件{suffix}").is_file(), suffix
        audit = data["audit"]
        assert audit["reportPath"] == str(tmp_path / "稿件.bime.audit.md") and audit["layoutVerified"] is False
        summary = json.loads((tmp_path / "稿件.bime.audit.json").read_text(encoding="utf-8"))["summary"]
        assert (audit["errors"], audit["warnings"], audit["manualChecks"]) == (
            summary["error"], summary["warning"], summary["manual"])
        with zipfile.ZipFile(data["path"]) as archive:
            assert "Ng" in archive.read("word/document.xml").decode("utf-8")
        assert _sha(document) == source
        assert not list(tmp_path.glob("稿件.ieee.*")), "bime_docx ignores the Style menu"
        again = await _call(service, "bibliography.export", _bime_params(context))
        assert again["path"] == data["path"], "a second export overwrites the first"
    asyncio.run(run())


@needs_pandoc
def test_bime_export_stops_on_a_key_missing_from_the_bibliography(tmp_path):
    async def run():
        service, _document, context = await _project(tmp_path, text="Claim [@ghost1999].\n")
        _write_library(tmp_path)
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", _bime_params(context))
        assert excinfo.value.code == "BIBLIOGRAPHY_FAILED" and "ghost1999" in str(excinfo.value)
        assert not (tmp_path / "稿件.bime.docx").exists()
    asyncio.run(run())


def _fake_bime(monkeypatch, *, returncode=0, errors=0, stdout=None, stderr=b""):
    """Stand in for the bime_word child process and record each call."""
    calls = []

    def fake_run(command, *, cwd, env, capture_output, timeout, check):
        calls.append({"command": command, "cwd": cwd, "env": env, "timeout": timeout})
        target = Path(command[command.index("-o") + 1])
        payload = b""
        if returncode in (0, 1):
            target.write_bytes(b"docx")
            payload = json.dumps({
                "output": str(target), "language": "zh",
                "audit": {"error": errors, "warning": 1, "conflict": 0, "unknown": 0, "manual": 3},
                "reports": [str(target.with_suffix(".audit.json")), str(target.with_suffix(".audit.md"))],
                "operation_report": str(target.with_suffix(".bime.json")), "layout_verified": False,
            }).encode("utf-8")
        return subprocess.CompletedProcess(command, returncode, payload if stdout is None else stdout, stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_bime_export_passes_the_profile_bibliography_and_overwrite(tmp_path, monkeypatch):
    async def run():
        service, document, context = await _project(tmp_path, text=CITED)
        library = _write_library(tmp_path)
        calls = _fake_bime(monkeypatch)
        await _call(service, "bibliography.export", _bime_params(context))
        (tmp_path / "bime-稿件-profile.json").write_text('{"language": "zh"}\n', encoding="utf-8")
        await _call(service, "bibliography.export", _bime_params(context))
        without, with_profile = (call["command"] for call in calls)
        assert without[:2] == [sys.executable, str(bime_export.vendor_script())]
        assert without[2:6] == ["convert", str(document), "-o", str(tmp_path / "稿件.bime.docx")]
        assert "--config" not in without
        assert with_profile[with_profile.index("--config") + 1] == str(tmp_path / "bime-稿件-profile.json")
        for command in (without, with_profile):
            assert command[command.index("--bibliography") + 1] == str(library)
            assert command[command.index("--scope") + 1] == "fragment" and command[-1] == "--overwrite"
        assert all(call["cwd"] == tmp_path and call["timeout"] == bime_export.BIME_TIMEOUT_SECONDS for call in calls)
        assert calls[0]["env"]["PATH"].split(":")[0] == str(Path(sys.executable).parent)
    asyncio.run(run())


def test_bime_export_refuses_unsaved_text_and_latex(tmp_path, monkeypatch):
    async def run():
        service, _document, context = await _project(tmp_path, text=CITED)
        _write_library(tmp_path)
        calls = _fake_bime(monkeypatch)
        edited = {**context, "editorRevision": 1, "sourceText": CITED + "Unsaved line.\n"}
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", _bime_params(edited))
        assert excinfo.value.code == "PROTOCOL_INVALID" and "Save the document first" in str(excinfo.value)
        tex = tmp_path / "thesis.tex"
        tex.write_text("\\cite{ng2021journal}\n", encoding="utf-8")
        tex_context = await service.dispatch("document.open", {"path": str(tex)})
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", _bime_params(tex_context))
        assert excinfo.value.code == "PROTOCOL_INVALID"
        assert calls == [] and not list(tmp_path.glob("*.bime.*"))
    asyncio.run(run())


def test_bime_export_with_audit_errors_still_returns_the_file(tmp_path, monkeypatch):
    async def run():
        service, _document, context = await _project(tmp_path, text=CITED)
        _write_library(tmp_path)
        _fake_bime(monkeypatch, returncode=1, errors=2)
        data = await _call(service, "bibliography.export", _bime_params(context))
        assert data["path"] == str(tmp_path / "稿件.bime.docx")
        assert data["audit"] == {"errors": 2, "warnings": 1, "manualChecks": 3,
                                 "reportPath": str(tmp_path / "稿件.bime.audit.md"), "layoutVerified": False}
    asyncio.run(run())


def test_bime_export_failures_show_the_bime_word_message(tmp_path, monkeypatch):
    async def run():
        service, _document, context = await _project(tmp_path, text=CITED)
        _write_library(tmp_path)
        cases = [
            ({"returncode": 2, "stderr": b"bime_word: Unknown config keys: colour\n"}, "Unknown config keys: colour"),
            ({"returncode": 1, "stdout": b"", "stderr": b"Missing Python dependency. No module named 'docx'"},
             "unexpected output (exit code 1): Missing Python dependency"),
            ({"returncode": 0, "stdout": b"not json"}, "unexpected output (exit code 0): not json"),
        ]
        for options, message in cases:
            _fake_bime(monkeypatch, **options)
            with pytest.raises(DesktopServiceError) as excinfo:
                await service.dispatch("bibliography.export", _bime_params(context))
            assert excinfo.value.code == "BIBLIOGRAPHY_FAILED" and message in str(excinfo.value), str(excinfo.value)

        def slow(command, **_kwargs):
            raise subprocess.TimeoutExpired(command, 180)
        monkeypatch.setattr(subprocess, "run", slow)
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", _bime_params(context))
        assert "did not finish within 180 s" in str(excinfo.value)
        monkeypatch.setattr(bime_export, "vendor_script", lambda: tmp_path / "missing" / "bime_word.py")
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", _bime_params(context))
        assert excinfo.value.code == "BIBLIOGRAPHY_FAILED" and "bundled bime_word is missing" in str(excinfo.value)
    asyncio.run(run())


def test_bibliography_failures_are_typed(tmp_path, monkeypatch):
    async def run():
        service, _document, context = await _project(tmp_path)
        (tmp_path / "references.json").write_text("{bad", encoding="utf-8")
        with pytest.raises(DesktopServiceError) as excinfo:
            await service.dispatch("bibliography.export", {"documentContext": context, "format": "markdown"})
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
