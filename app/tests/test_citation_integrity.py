"""Integrity report: uses, order, missing/uncited keys, duplicates, verification."""

import asyncio
import json

from skills.citation.hub import CitationProviderHub
from skills.citation.integrity import bundle_checker, inspect
from skills.citation.resolution import WorkIdentifier, WorkIntent
from skills.citation.service import CitationService
from tests.test_citation_doi_first_save import JOURNAL_DOI, Fetcher

ITEMS = [
    {"id": "ng2021journal", "type": "article-journal", "title": "A Journal Article",
     "author": [{"family": "Ng", "given": "Kim"}], "issued": {"date-parts": [[2021]]},
     "DOI": JOURNAL_DOI},
    {"id": "hand2019note", "type": "webpage", "title": "Hand note",
     "author": [{"literal": "Plant Lab"}], "issued": {"date-parts": [[2019]]}},
    {"id": "dup2021copy", "type": "article-journal", "title": "Copy",
     "DOI": JOURNAL_DOI.upper()},
    {"id": "never2000cited", "type": "book", "title": "Unused"},
]


def _library(tmp_path, items=ITEMS):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


TEXT = "Intro [@hand2019note; @ng2021journal].\nThen @ghost and @ng2021journal again [@ghost2]."


def test_report_lists_uses_order_missing_uncited_and_duplicates(tmp_path):
    report = inspect(TEXT, "markdown", _library(tmp_path))
    assert report["bibliography"]["status"] == "ok"
    assert report["order"] == ["hand2019note", "ng2021journal", "ghost", "ghost2"]
    assert [m["key"] for m in report["missing"]] == ["ghost", "ghost2"]
    assert report["missing"][0]["uses"] == [{"start": 44, "end": 50, "line": 2}]
    assert report["uncited"] == ["dup2021copy", "never2000cited"]
    assert report["duplicateDois"] == [{"doi": JOURNAL_DOI, "keys": ["ng2021journal", "dup2021copy"]}]
    entries = {e["key"]: e for e in report["entries"]}
    assert entries["ng2021journal"]["citedCount"] == 2
    assert entries["ng2021journal"]["firstUse"] == 1
    assert entries["hand2019note"]["authors"] == ["Plant Lab"]
    assert entries["never2000cited"]["firstUse"] is None
    assert [u["known"] for u in report["uses"]] == [True, True, False, True, False]


def test_verification_comes_from_valid_bundles(tmp_path):
    cite = tmp_path / "cite"
    service = CitationService(CitationProviderHub(env={}, fetcher=Fetcher()), output_dir=cite)
    asyncio.run(service.save((WorkIntent("x", identifiers=(WorkIdentifier("doi", JOURNAL_DOI),)),)))
    report = inspect(TEXT, "markdown", _library(tmp_path), bundle_checker(cite))
    status = {e["key"]: e["verification"] for e in report["entries"]}
    assert status == {
        "ng2021journal": "verified",
        "hand2019note": "unverified",
        "dup2021copy": "verified",
        "never2000cited": "unverified",
    }


def test_tampered_bundle_is_not_verified(tmp_path):
    cite = tmp_path / "cite"
    service = CitationService(CitationProviderHub(env={}, fetcher=Fetcher()), output_dir=cite)
    asyncio.run(service.save((WorkIntent("x", identifiers=(WorkIdentifier("doi", JOURNAL_DOI),)),)))
    bib = next(cite.glob("*/reference.bib"))
    bib.write_text(bib.read_text() + "% tampered\n")
    report = inspect(TEXT, "markdown", _library(tmp_path), bundle_checker(cite))
    assert {e["verification"] for e in report["entries"]} == {"unverified"}


def test_malformed_bibliography_is_reported_not_raised(tmp_path):
    path = tmp_path / "references.json"
    path.write_text("{}", encoding="utf-8")
    report = inspect(TEXT, "markdown", path)
    assert report["bibliography"]["status"] == "error"
    assert report["bibliography"]["error"]["code"] == "library_malformed"
    assert report["entries"] == [] and report["missing"] == []
    assert report["order"] == ["hand2019note", "ng2021journal", "ghost", "ghost2"]
    assert {u["known"] for u in report["uses"]} == {None}


def test_missing_bibliography_reports_every_key_missing(tmp_path):
    report = inspect("[@a] @b", "markdown", tmp_path / "references.json")
    assert report["bibliography"]["status"] == "missing"
    assert [m["key"] for m in report["missing"]] == ["a", "b"]


def test_latex_report(tmp_path):
    report = inspect("\\cite{ng2021journal,nope}", "latex", _library(tmp_path))
    assert report["format"] == "latex"
    assert [m["key"] for m in report["missing"]] == ["nope"]
