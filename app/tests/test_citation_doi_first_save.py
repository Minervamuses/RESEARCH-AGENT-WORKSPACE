"""DOI-first saving: a visible search record's DOI goes straight to exact
verification, and the saved receipt keeps that record's identity and version."""

import asyncio
import json

import pytest

from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse
from skills.citation.resolution import WorkIdentifier, WorkIntent
from skills.citation.service import CitationService

PREPRINT_DOI = "10.1101/2020.03.22.002386"
JOURNAL_DOI = "10.1038/s41586-021-03819-2"
POSTED_DOI = "10.31219/osf.io/abcde"

# Crossref works items and the matching doi.org CSL JSON (which keeps
# Crossref's type/subtype/relation fields, as checked against live doi.org).
CROSSREF = {
    PREPRINT_DOI: {
        "DOI": PREPRINT_DOI, "title": ["A bioRxiv Preprint"],
        "author": [{"given": "Pat", "family": "Lee"}],
        "issued": {"date-parts": [[2020]]}, "type": "posted-content",
        "subtype": "preprint", "score": 9.0,
    },
    JOURNAL_DOI: {
        "DOI": JOURNAL_DOI, "title": ["A Journal Article"],
        "author": [{"given": "Kim", "family": "Ng"}],
        "issued": {"date-parts": [[2021]]}, "container-title": ["Nature"],
        "type": "journal-article", "score": 8.0,
    },
    POSTED_DOI: {
        "DOI": POSTED_DOI, "title": ["A Posted Working Paper"],
        "issued": {"date-parts": [[2019]]}, "type": "posted-content",
        "score": 7.0,
    },
}
CSL = {
    PREPRINT_DOI: {
        "DOI": PREPRINT_DOI, "title": "A bioRxiv Preprint",
        "author": [{"given": "Pat", "family": "Lee"}],
        "issued": {"date-parts": [[2020]]}, "type": "posted-content",
        "subtype": "preprint", "container-title": [],
    },
    JOURNAL_DOI: {
        "DOI": JOURNAL_DOI, "title": "A Journal Article",
        "author": [{"given": "Kim", "family": "Ng"}],
        "issued": {"date-parts": [[2021]]}, "type": "journal-article",
        "container-title": "Nature",
    },
    POSTED_DOI: {
        "DOI": POSTED_DOI, "title": "A Posted Working Paper",
        "issued": {"date-parts": [[2019]]}, "type": "posted-content",
    },
}


class Fetcher:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, url, headers):
        accept = headers.get("Accept", "")
        self.calls.append((url, accept))
        if "api.crossref.org" in url:
            items = list(CROSSREF.values())
            return FetchResponse(200, body=json.dumps({"message": {"items": items}}).encode())
        if "api.datacite.org" in url:
            return FetchResponse(200, body=b'{"data": []}')
        doi = url.removeprefix("https://doi.org/")
        if doi in CSL and "csl+json" in accept:
            return FetchResponse(200, body=json.dumps(CSL[doi]).encode())
        if doi in CSL and "x-bibtex" in accept:
            title = CSL[doi]["title"]
            return FetchResponse(200, body=(
                f"@misc{{k, title={{{title}}}, year={{2020}}, doi={{{doi}}}}}"
            ).encode())
        raise AssertionError(f"unexpected url: {url}")


def _service(tmp_path, fetcher):
    return CitationService(
        CitationProviderHub(env={}, fetcher=fetcher), output_dir=tmp_path / "cite",
    )


@pytest.mark.parametrize(
    ("doi", "version"),
    [(PREPRINT_DOI, "preprint"), (JOURNAL_DOI, "published"), (POSTED_DOI, "repost")],
)
def test_doi_only_save_keeps_the_search_records_version(tmp_path, doi, version):
    fetcher = Fetcher()
    service = _service(tmp_path, fetcher)
    records, _states = asyncio.run(service.search("paper"))
    searched = next(record for record in records if record.doi == doi)

    outcome = asyncio.run(service.save((
        WorkIntent("selected", identifiers=(WorkIdentifier("doi", doi),)),
    )))

    receipt = outcome.items[0].receipt
    assert outcome.items[0].status == "saved"
    assert receipt.doi == searched.doi
    assert receipt.title == searched.title
    assert receipt.year == searched.year
    assert receipt.version_kind == version
    if searched.version_kind != "unknown":
        assert receipt.version_kind == searched.version_kind
    sidecar = json.loads(
        (tmp_path / "cite").joinpath(receipt.bundle_path, "citation.json").read_text()
    )
    assert sidecar["resolution"]["version_kind"] == version


def test_two_turn_selection_saves_the_chosen_record_by_doi_only(monkeypatch, tmp_path):
    """Turn 1 searches and lists records; turn 2's "第 2 篇" is resolved from
    the visible list and saved with only its DOI: no fuzzy provider search,
    and the receipt matches the second listed record."""
    import re

    from langchain_core.messages import AIMessage, HumanMessage

    from tests.test_citation_e2e import (
        _fixture_services,
        _make_session,
        _save_content,
        _workflow_call,
        _workflow_results,
    )

    class SelectionModel:
        def __init__(self):
            self.save_args = None
            self.receipt = None

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            return self.invoke(messages)

        def invoke(self, messages):
            request = [m for m in messages if isinstance(m, HumanMessage)][-1].content
            results = _workflow_results(messages)
            if "搜尋" in request:
                if not results:
                    return _workflow_call({"action": "search", "query": "paper"}, "search-1")
                # Present the record blocks verbatim, DOIs included.
                listing = results[-1].content.split("\nProvider states:")[0]
                return AIMessage(content="搜尋結果：\n" + listing.split("\n", 1)[1])
            if not results:
                prior = next(
                    m.content for m in reversed(messages)
                    if isinstance(m, AIMessage) and m.content.startswith("搜尋結果")
                )
                block = prior.split("\n2. ", 1)[1].split("\n3. ", 1)[0]
                doi = re.search(r"DOI: (\S+)", block).group(1)
                self.save_args = {
                    "action": "save",
                    "works": [{
                        "requested_label": "第 2 篇",
                        "identifiers": [{"kind": "doi", "value": doi}],
                    }],
                }
                return _workflow_call(self.save_args, "save-1")
            item = _save_content(results[-1]).items[0]
            self.receipt = item.receipt
            return AIMessage(content=f"已保存：{item.status}")

    model = SelectionModel()
    session = _make_session(monkeypatch, tmp_path, model)
    fetcher = Fetcher()
    _fixture_services(monkeypatch, tmp_path, fetcher=fetcher)

    asyncio.run(session.turn("/citation 搜尋 paper", skill_name="citation"))
    listing = session.recent_turns[-1].assistant_output
    second_block = listing.split("\n2. ", 1)[1].split("\n3. ", 1)[0]
    calls_before_save = len(fetcher.calls)

    answer = asyncio.run(session.turn("保存第 2 篇", skill_name="citation"))

    save_calls = fetcher.calls[calls_before_save:]
    assert answer == "已保存：saved"
    assert all(url.startswith("https://doi.org/") for url, _accept in save_calls)
    assert sorted(accept for _url, accept in save_calls) == [
        "application/vnd.citationstyles.csl+json", "application/x-bibtex",
    ]
    work = model.save_args["works"][0]
    assert set(work) == {"requested_label", "identifiers"}
    receipt = model.receipt
    assert f"DOI: {receipt.doi}" in second_block
    assert receipt.title in second_block.splitlines()[0]
    assert f"year: {receipt.year};" in second_block
    assert f"version: {receipt.version_kind}" in second_block
