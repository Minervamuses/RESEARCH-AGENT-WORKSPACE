"""/citation saves in a desktop project merge into the project bibliography."""

import asyncio
import json
import os

import pytest

from agent.config import AgentConfig
from agent.desktop.catalog import (
    CatalogMalformedError,
    inspect_project,
    project_citation_settings,
)
from agent.skills.citation.session_policy import CitationSessionPolicy
from skills.citation.hub import CitationProviderHub
from skills.citation.resolution import WorkIdentifier, WorkIntent
from skills.citation.service import CitationService
from skills.citation.tool import create_citation_workflow_tool
from tests.test_citation_doi_first_save import JOURNAL_DOI, PREPRINT_DOI, Fetcher

HAND_WRITTEN = [
    {
        "id": "ng2021handpicked",
        "type": "article-journal",
        "title": "A Journal Article — hand written",
        "author": [{"family": "Ng", "given": "Kim"}],
        "issued": {"date-parts": [[2021]]},
        "DOI": JOURNAL_DOI.upper(),
    },
    {
        "id": "lab2020site",
        "type": "webpage",
        "title": "Lab site",
        "author": [{"literal": "Plant Lab"}],
        "URL": "https://example.org/",
    },
]


def _library(tmp_path, items=HAND_WRITTEN):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def _tool(service):
    return create_citation_workflow_tool(service_getter=lambda: service)


def _save(tool, doi):
    return asyncio.run(tool.ainvoke({
        "type": "tool_call", "id": "c1", "name": "citation_workflow",
        "args": {"action": "save", "works": [{"requested_label": "pick", "identifiers": [{"kind": "doi", "value": doi}]}]},
    }))


def _service(tmp_path, library_path=None):
    return CitationService(
        CitationProviderHub(env={}, fetcher=Fetcher()),
        output_dir=tmp_path / "cite",
        library_path=library_path,
    )


def test_project_save_adds_one_entry_and_reports_its_key(tmp_path):
    path = _library(tmp_path)
    before = path.read_text(encoding="utf-8")
    message = _save(_tool(_service(tmp_path, path)), PREPRINT_DOI)

    item = message.artifact["items"][0]
    assert item["status"] == "saved"
    assert item["bibliography"] == {
        "status": "added", "path": str(path), "key": "lee2020biorxiv", "reason_code": None,
    }
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before[: before.rindex(" }")])
    data = json.loads(after)
    assert data[:2] == HAND_WRITTEN
    assert data[2]["id"] == "lee2020biorxiv"
    assert data[2]["DOI"] == PREPRINT_DOI
    assert data[2]["type"] == "article"  # posted-content mapped
    assert "abstract" not in data[2]
    assert "key lee2020biorxiv (added)" in message.content
    assert "[@key]" in message.content and "\\cite{key}" in message.content
    assert str(path) in message.content


def test_resaving_is_a_no_op_with_the_same_key(tmp_path):
    path = _library(tmp_path)
    tool = _tool(_service(tmp_path, path))
    _save(tool, PREPRINT_DOI)
    snapshot = path.read_bytes()
    message = _save(_tool(_service(tmp_path, path)), PREPRINT_DOI)
    item = message.artifact["items"][0]
    assert item["status"] == "reused"
    assert item["bibliography"]["status"] == "existing"
    assert item["bibliography"]["key"] == "lee2020biorxiv"
    assert path.read_bytes() == snapshot


def test_hand_written_entry_with_same_doi_is_reused_unchanged(tmp_path):
    path = _library(tmp_path)
    snapshot = path.read_bytes()
    message = _save(_tool(_service(tmp_path, path)), JOURNAL_DOI)
    link = message.artifact["items"][0]["bibliography"]
    assert (link["status"], link["key"]) == ("existing", "ng2021handpicked")
    assert path.read_bytes() == snapshot


def test_bibliography_failure_keeps_the_bundle_outcome(tmp_path):
    path = tmp_path / "references.json"
    path.write_text('{"not": "an array"}', encoding="utf-8")
    message = _save(_tool(_service(tmp_path, path)), PREPRINT_DOI)
    item = message.artifact["items"][0]
    assert item["status"] == "saved"
    assert item["bibliography"] == {
        "status": "failed", "path": str(path), "key": None, "reason_code": "library_malformed",
    }
    assert path.read_text(encoding="utf-8") == '{"not": "an array"}'
    assert "not added to the bibliography (library_malformed)" in message.content


def test_cli_save_has_no_bibliography(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    message = _save(_tool(_service(tmp_path)), PREPRINT_DOI)
    assert "bibliography" not in message.artifact["items"][0]
    assert message.content.startswith("Actual citation save result:\n")
    json.loads(message.content.removeprefix("Actual citation save result:\n"))
    assert not list(tmp_path.glob("*.json"))


def test_session_policy_passes_the_project_bibliography(tmp_path, monkeypatch):
    built = []

    def create(hub, *, config, **kwargs):
        built.append(kwargs)
        return object()

    monkeypatch.setattr("skills.citation.hub.get_provider_hub", lambda: object())
    monkeypatch.setattr("skills.citation.service.CitationService", create)
    cli = CitationSessionPolicy(AgentConfig())
    assert cli.bibliography_path() is None
    cli.service
    project = CitationSessionPolicy(AgentConfig(), bibliography_path=lambda: tmp_path / "references.json")
    project.service
    assert built == [{}, {"library_path": tmp_path / "references.json"}]


# --- RESEARCH.md metadata -------------------------------------------------


def _research(tmp_path, metadata):
    (tmp_path / "RESEARCH.md").write_text(
        "# Project\n\n<!-- research-agent-project\n" + json.dumps(metadata) + "\n-->\n",
        encoding="utf-8",
    )


def _meta(**extra):
    return {"version": 1, "historyDirectory": "history", **extra}


def test_default_bibliography_is_references_json_in_the_root(tmp_path):
    _research(tmp_path, _meta())
    settings = project_citation_settings(tmp_path)
    assert settings == {"bibliographyPath": tmp_path.resolve() / "references.json", "citationStyle": None}


def test_bibliography_and_citation_style_metadata_are_accepted(tmp_path):
    _research(tmp_path, _meta(bibliography="refs/thesis.json", citationStyle="apa"))
    assert inspect_project(str(tmp_path), tmp_path / "store")["status"] in {"ready", "needs_initialization"}
    settings = project_citation_settings(tmp_path)
    assert settings["bibliographyPath"] == tmp_path.resolve() / "refs" / "thesis.json"
    assert settings["citationStyle"] == "apa"


@pytest.mark.parametrize("metadata", [
    _meta(bibliography="../outside.json"),
    _meta(bibliography="/abs/references.json"),
    _meta(bibliography="refs/../../x.json"),
    _meta(bibliography="references.bib"),
    _meta(bibliography="~/x.json"),
    _meta(bibliography=""),
    _meta(bibliography=7),
    _meta(citationStyle=""),
    _meta(citationStyle=3),
    _meta(unknownKey="x"),
])
def test_invalid_metadata_is_malformed(tmp_path, metadata):
    _research(tmp_path, metadata)
    with pytest.raises(CatalogMalformedError):
        inspect_project(str(tmp_path), tmp_path / "store")
    with pytest.raises(CatalogMalformedError):
        project_citation_settings(tmp_path)


def test_bibliography_symlink_escaping_the_root_is_malformed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("[]\n")
    os.symlink(outside, root / "references.json")
    _research(root, _meta())
    with pytest.raises(CatalogMalformedError):
        project_citation_settings(root)


def test_initialize_project_still_writes_only_two_keys(tmp_path):
    from agent.desktop.catalog import initialize_project

    root = tmp_path / "project"
    root.mkdir()
    preview = inspect_project(str(root), tmp_path / "store")
    initialize_project(
        str(root), tmp_path / "store",
        history_directory=preview["historyDirectory"],
        expected_fingerprint=preview["researchFingerprint"],
    )
    text = (root / "RESEARCH.md").read_text(encoding="utf-8")
    payload = text.split("<!-- research-agent-project", 1)[1].split("-->", 1)[0]
    assert set(json.loads(payload)) == {"version", "historyDirectory"}


# --- desktop wiring -----------------------------------------------------------


def test_desktop_citation_turn_merges_into_the_project_bibliography(monkeypatch, tmp_path):
    from test_desktop_conversations import _citation_desktop, _dispatch_citation_approved
    from test_desktop_service import _open_test_project, _turn_params

    service, _model, _fetcher, services, _sessions = _citation_desktop(monkeypatch, tmp_path)
    asyncio.run(_open_test_project(service, tmp_path))
    asyncio.run(service.dispatch("session.create", {"loadMcp": False}))
    events = []
    asyncio.run(_dispatch_citation_approved(
        service, _turn_params("/citation 搜尋 Paper A，保存並正式引用"), events,
    ))
    library = tmp_path.resolve() / "references.json"
    approvals = [data for event, data in events if event == "approval.required"]
    assert len(approvals) == 1
    assert str(library) in approvals[0]["description"]
    assert services and services[0].library_path == library
    data = json.loads(library.read_text(encoding="utf-8"))
    assert len(data) == 1 and data[0]["id"]
    assert "abstract" not in data[0]
