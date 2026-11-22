"""/citation saves in a desktop project merge into the project bibliography."""

import asyncio
import json
import os

import pytest
from langchain_core.messages import ToolMessage

from agent.desktop.project import (
    ProjectMalformedError,
    inspect_project,
    project_citation_settings,
)
from agent.skills.citation.session_policy import CitationSessionPolicy
from skills.citation import service as service_module
from skills.citation.gate import check_citations
from skills.citation.hub import CitationProviderHub
from skills.citation.library import LIBRARY_WRITE_FAILED, LibraryError
from skills.citation.render import render_citations
from skills.citation.resolution import WorkIdentifier, WorkIntent
from skills.citation.service import CitationService
from skills.citation.tool import create_citation_workflow_tool
from skills.citation.types import CanonicalIdentity, SourceRef, is_citable_source, source_id_for
from tests.test_citation_doi_first_save import JOURNAL_DOI, POSTED_DOI, PREPRINT_DOI, Fetcher

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
        library_path=library_path,
    )


def test_project_save_adds_one_entry_and_reports_its_key(tmp_path):
    path = _library(tmp_path)
    before = path.read_text(encoding="utf-8")
    message = _save(_tool(_service(tmp_path, path)), PREPRINT_DOI)

    item = message.artifact["items"][0]
    assert item["status"] == "saved"
    assert item["bibliography"] == {"status": "added", "path": str(path), "key": "lee2020biorxiv"}
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before[: before.rindex(" }")])
    data = json.loads(after)
    assert data[:2] == HAND_WRITTEN
    assert data[2]["id"] == "lee2020biorxiv"
    assert data[2]["DOI"] == PREPRINT_DOI
    assert data[2]["type"] == "article"  # posted-content mapped
    assert "abstract" not in data[2]
    assert "key lee2020biorxiv (saved)" in message.content
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


def test_unreadable_bibliography_is_storage_failed_and_not_citable(tmp_path):
    path = tmp_path / "references.json"
    path.write_text('{"not": "an array"}', encoding="utf-8")
    service = _service(tmp_path, path)
    message = _save(_tool(service), PREPRINT_DOI)
    item = message.artifact["items"][0]
    assert (item["status"], item["reason_code"]) == ("storage_failed", "library_malformed")
    assert item["receipt"] is None and item["bibliography"] is None
    assert service.registry.list() == []
    assert path.read_text(encoding="utf-8") == '{"not": "an array"}'
    assert "NOT saved and not citable in this task (library_malformed)" in message.content


def test_cli_save_is_verified_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = _service(tmp_path)
    message = _save(_tool(service), PREPRINT_DOI)
    item = message.artifact["items"][0]
    assert (item["status"], item["reason_code"]) == ("verified", "verified_not_persisted")
    assert item["bibliography"] is None and item["receipt"] is not None
    assert message.content.startswith("Actual citation save result:\n")
    assert "verified and citable in this conversation only" in message.content
    assert "nothing was written to disk" in message.content
    assert list(tmp_path.iterdir()) == []


def test_session_policy_passes_the_project_bibliography(tmp_path, monkeypatch):
    built = []

    def create(hub, **kwargs):
        built.append(kwargs)
        return object()

    monkeypatch.setattr("skills.citation.hub.get_provider_hub", lambda: object())
    monkeypatch.setattr("skills.citation.service.CitationService", create)
    cli = CitationSessionPolicy()
    assert cli.bibliography_path() is None
    cli.service
    project = CitationSessionPolicy(bibliography_path=lambda: tmp_path / "references.json")
    project.service
    assert built == [{"library_path": None}, {"library_path": tmp_path / "references.json"}]


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
    with pytest.raises(ProjectMalformedError):
        inspect_project(str(tmp_path), tmp_path / "store")
    with pytest.raises(ProjectMalformedError):
        project_citation_settings(tmp_path)


def test_bibliography_symlink_escaping_the_root_is_malformed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("[]\n")
    os.symlink(outside, root / "references.json")
    _research(root, _meta())
    with pytest.raises(ProjectMalformedError):
        project_citation_settings(root)


def test_initialize_project_still_writes_only_two_keys(tmp_path):
    from agent.desktop.project import initialize_project

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


# --- Save semantics: citable only once in the bibliography (U13, U20, P13) -----



def _batch(service, *dois):
    return asyncio.run(service.save(tuple(
        WorkIntent(f"pick {index}", identifiers=(WorkIdentifier("doi", doi),))
        for index, doi in enumerate(dois)
    )))


def _metrics(service, outcome):
    policy = CitationSessionPolicy()
    policy._service = service
    message = ToolMessage(
        content="result", name="citation_workflow", tool_call_id="save-1",
        artifact=outcome.to_artifact(),
    )
    return policy.save_metrics([message], citation_active=True)


def _gate_passes(service, marker):
    citable = {ref.source_id for ref in service.registry.list() if is_citable_source(ref)}
    return check_citations(marker, verified_source_ids=citable, citation_active=True) == []


def _fail_bibliography_writes(monkeypatch):
    writes = []

    def write(library):
        writes.append(library)
        raise LibraryError(LIBRARY_WRITE_FAILED, "read-only project folder")

    monkeypatch.setattr(service_module, "write_library_atomic", write)
    return writes


def _files(root):
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def test_desktop_save_rewrites_only_the_bibliography(tmp_path):
    # (a) No cite/, reference.bib, or citation.json: the bibliography is the only store.
    path = _library(tmp_path)
    before = _files(tmp_path)
    outcome = _batch(_service(tmp_path, path), PREPRINT_DOI)
    assert outcome.items[0].status == "saved"
    assert _files(tmp_path) == before == ["references.json"]


def test_bibliography_write_failure_is_storage_failed_and_not_citable(tmp_path, monkeypatch):
    # (b)
    path = _library(tmp_path)
    original = path.read_bytes()
    _fail_bibliography_writes(monkeypatch)
    service = _service(tmp_path, path)
    tool = _tool(service)
    message = _save(tool, PREPRINT_DOI)
    item = message.artifact["items"][0]
    assert (item["status"], item["reason_code"]) == ("storage_failed", LIBRARY_WRITE_FAILED)
    assert item["receipt"] is None
    marker = f"[[cite:{source_id_for(CanonicalIdentity('doi', PREPRINT_DOI))}]]"
    assert not _gate_passes(service, marker)
    assert "NOT saved and not citable in this task" in message.content
    assert "the save can be retried" in message.content
    outcome = service_module.SaveBatchOutcome.from_artifact(message.artifact)
    metrics = _metrics(service, outcome)
    assert (metrics.failed_count, metrics.new_saved_count, metrics.verified_count) == (1, 0, 0)
    assert path.read_bytes() == original


def test_existing_work_is_reused_with_its_key_and_citable(tmp_path):
    # (c)
    path = _library(tmp_path)
    service = _service(tmp_path, path)
    item = _batch(service, JOURNAL_DOI).items[0]
    assert (item.status, item.reason_code) == ("reused", "reused_existing")
    assert item.bibliography.key == "ng2021handpicked"
    assert _gate_passes(service, item.receipt.cite_marker)


def test_duplicate_work_in_one_batch_is_saved_once_then_reused(tmp_path):
    # (d)
    path = _library(tmp_path)
    service = _service(tmp_path, path)
    outcome = _batch(service, PREPRINT_DOI, PREPRINT_DOI)
    first, second = outcome.items
    assert (first.status, second.status) == ("saved", "reused")
    assert first.bibliography.key == second.bibliography.key == "lee2020biorxiv"
    assert [entry["id"] for entry in json.loads(path.read_text(encoding="utf-8"))].count("lee2020biorxiv") == 1
    metrics = _metrics(service, outcome)
    assert (metrics.new_saved_count, metrics.reused_count, metrics.failed_count) == (1, 1, 0)


def test_duplicate_work_in_a_failed_write_is_never_reported_reused(tmp_path, monkeypatch):
    # (e)
    path = _library(tmp_path)
    _fail_bibliography_writes(monkeypatch)
    service = _service(tmp_path, path)
    outcome = _batch(service, PREPRINT_DOI, PREPRINT_DOI)
    assert [(item.status, item.reason_code) for item in outcome.items] == [
        ("storage_failed", LIBRARY_WRITE_FAILED), ("storage_failed", LIBRARY_WRITE_FAILED),
    ]
    assert service.registry.list() == []


def test_one_rejected_merge_does_not_stop_the_other_work_and_writes_once(tmp_path, monkeypatch):
    # (f)
    path = _library(tmp_path)
    merge = service_module.merge_library
    writes = []
    write = service_module.write_library_atomic

    def reject_posted(library, item):
        if item.get("DOI") == POSTED_DOI:
            raise LibraryError("library_conflict", "no free key")
        return merge(library, item)

    def counted_write(library):
        writes.append(library)
        return write(library)

    monkeypatch.setattr(service_module, "merge_library", reject_posted)
    monkeypatch.setattr(service_module, "write_library_atomic", counted_write)
    outcome = _batch(_service(tmp_path, path), POSTED_DOI, PREPRINT_DOI)
    assert [(item.status, item.reason_code) for item in outcome.items] == [
        ("storage_failed", "library_conflict"), ("saved", "saved_new"),
    ]
    assert len(writes) == 1
    assert POSTED_DOI not in path.read_text(encoding="utf-8")


def test_cli_save_is_verified_citable_in_the_task_and_writes_no_file(tmp_path, monkeypatch):
    # (g)
    monkeypatch.chdir(tmp_path)
    service = _service(tmp_path)
    outcome = _batch(service, PREPRINT_DOI)
    item = outcome.items[0]
    assert (item.status, item.bibliography) == ("verified", None)
    assert list(tmp_path.iterdir()) == []
    assert _gate_passes(service, item.receipt.cite_marker)
    rendered = render_citations(f"Claim {item.receipt.cite_marker}.", resolve=service.registry.get)
    assert "Claim [1]." in rendered and f"DOI: {PREPRINT_DOI}" in rendered
    metrics = _metrics(service, outcome)
    assert (metrics.verified_count, metrics.new_saved_count, metrics.failed_count) == (1, 0, 0)


def test_cli_saving_the_same_work_twice_in_one_task_stays_verified(tmp_path):
    # (h)
    service = _service(tmp_path)
    first = _batch(service, PREPRINT_DOI).items[0]
    second = _batch(service, PREPRINT_DOI).items[0]
    assert (first.status, second.status) == ("verified", "verified")
    assert first.receipt == second.receipt
    assert _gate_passes(service, second.receipt.cite_marker)


def test_registry_conflict_is_identity_conflict_and_never_written(tmp_path):
    # (i) P13: the source ID already belongs to another identity in this task.
    path = _library(tmp_path)
    original = path.read_bytes()
    service = _service(tmp_path, path)
    sid = source_id_for(CanonicalIdentity("doi", PREPRINT_DOI))
    service.registry.register(SourceRef(
        sid, "10.9999/other", "Another work",
        verification_level="doi_identity_verified",
        canonical_identity=CanonicalIdentity("doi", "10.9999/other"),
    ))
    item = _batch(service, PREPRINT_DOI).items[0]
    assert (item.status, item.reason_code) == ("identity_conflict", "registry_conflict")
    assert item.receipt is None
    assert path.read_bytes() == original


def test_existing_work_stays_reused_when_a_new_work_in_the_batch_fails_to_write(tmp_path, monkeypatch):
    # (k) U20: A was in the bibliography before the batch; B is new and its write fails.
    path = _library(tmp_path)
    original = path.read_bytes()
    _fail_bibliography_writes(monkeypatch)
    service = _service(tmp_path, path)
    outcome = _batch(service, JOURNAL_DOI, PREPRINT_DOI)
    existing, new = outcome.items
    assert (existing.status, existing.reason_code) == ("reused", "reused_existing")
    assert existing.bibliography.key == "ng2021handpicked"
    assert existing.receipt is not None and _gate_passes(service, existing.receipt.cite_marker)
    assert (new.status, new.reason_code, new.receipt) == ("storage_failed", LIBRARY_WRITE_FAILED, None)
    assert not _gate_passes(service, f"[[cite:{source_id_for(CanonicalIdentity('doi', PREPRINT_DOI))}]]")
    metrics = _metrics(service, outcome)
    assert (metrics.reused_count, metrics.new_saved_count, metrics.failed_count) == (1, 0, 1)
    assert path.read_bytes() == original
