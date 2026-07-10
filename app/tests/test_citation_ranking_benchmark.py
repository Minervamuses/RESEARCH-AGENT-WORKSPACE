"""Ranking benchmark on frozen provider/expander fixtures.

Acceptance (plan):
  * every DOI and exact-title case lands in the top 10 on the FIRST search;
  * Topic Recall@10 over first search + one /citation more strictly exceeds
    the frozen baseline artifact (tests/fixtures/ranking_baseline.json);
  * zero false saves on the gold corpus: only intentional confirms of
    relevant DOIs produce bundles, and no-DOI / failed confirms write none.

Everything is deterministic: fixed provider fixtures, a fixed expander
fixture, and the fixed RRF tie-break.
"""

import asyncio
import json
import urllib.parse
from pathlib import Path

from citation.coordinator import CitationCoordinator
from citation.hub import CitationProviderHub
from citation.providers.net import FetchResponse

BASELINE_PATH = Path(__file__).parent / "fixtures" / "ranking_baseline.json"

# --- gold corpus -------------------------------------------------------------

RELEVANT = [f"10.1234/rel-{i}" for i in range(6)]
NOISE = [f"10.9999/noise-{i}" for i in range(8)]

EXACT_TITLE_CASES = [
    ("Attention Is All You Need", "10.4855/attention"),
    ("Dense Passage Retrieval for Open-Domain Question Answering", "10.4855/dpr"),
    ("大規模語言模型檢索增強survey", "10.4855/zh-survey"),
]

DOI_CASES = ["10.4855/attention", "10.1234/rel-0"]

TOPIC_QUERY = "retrieval efficiency"
TOPIC_EXPANSION = "efficient dense retrieval"

TITLES = {
    "10.4855/attention": "Attention Is All You Need",
    "10.4855/dpr": "Dense Passage Retrieval for Open-Domain Question Answering",
    "10.4855/zh-survey": "大規模語言模型檢索增強survey",
    **{doi: f"Relevant Work {i}" for i, doi in enumerate(RELEVANT)},
    **{doi: f"Noise Work {i}" for i, doi in enumerate(NOISE)},
}


def _crossref_item(doi, rank):
    return {
        "DOI": doi,
        "title": [TITLES[doi]],
        "issued": {"date-parts": [[2021]]},
        "score": 50.0 - rank,
    }


def _openalex_result(doi, rank):
    return {
        "id": f"https://openalex.org/W{abs(hash(doi)) % 10**8}",
        "doi": f"https://doi.org/{doi}",
        "display_name": TITLES[doi],
        "publication_year": 2021,
        "relevance_score": 100.0 - rank,
    }


# Frozen provider fixtures per query. Crossref sees 4 relevant works diluted
# with noise; OpenAlex re-ranks and adds a 5th; the expansion adds nothing
# new; only the explicit web 'more' surfaces the 6th.
CROSSREF_FIXTURE = {
    TOPIC_QUERY: [
        _crossref_item(d, i)
        for i, d in enumerate([
            NOISE[0], RELEVANT[0], NOISE[1], RELEVANT[1], NOISE[2],
            RELEVANT[2], NOISE[3], NOISE[4], RELEVANT[3], NOISE[5],
        ])
    ],
    TOPIC_EXPANSION: [
        _crossref_item(d, i)
        for i, d in enumerate([RELEVANT[0], NOISE[6], RELEVANT[2]])
    ],
    **{
        title: [_crossref_item(doi, 0), _crossref_item(NOISE[7], 1)]
        for title, doi in EXACT_TITLE_CASES
    },
}

OPENALEX_FIXTURE = {
    TOPIC_QUERY: [
        _openalex_result(d, i)
        for i, d in enumerate([RELEVANT[4], RELEVANT[1], NOISE[6], RELEVANT[0]])
    ],
    TOPIC_EXPANSION: [],
    **{title: [_openalex_result(doi, 0)] for title, doi in EXACT_TITLE_CASES},
}

WEB_FIXTURE = {
    TOPIC_QUERY: (
        "**1. Relevant Work 5 landing page**\n"
        f"URL: https://example.org/rel-5?doi={RELEVANT[5]}\n"
        f"Description: DOI: {RELEVANT[5]}\n"
    ),
}

EXPANSION_FIXTURE = {TOPIC_QUERY: [TOPIC_EXPANSION]}


class BenchmarkFetcher:
    """Deterministic transport routing by URL, keyed on the fixtures above."""

    async def __call__(self, url, headers):
        accept = headers.get("Accept", "")
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if "api.crossref.org" in url:
            query = params.get("query.bibliographic", [""])[0]
            items = CROSSREF_FIXTURE.get(query, [])
            return FetchResponse(
                status=200,
                body=json.dumps({"message": {"items": items}}).encode(),
            )
        if "api.openalex.org" in url:
            query = params.get("search", [""])[0]
            results = OPENALEX_FIXTURE.get(query, [])
            return FetchResponse(
                status=200, body=json.dumps({"results": results}).encode()
            )
        if url.startswith("https://doi.org/ra/"):
            return FetchResponse(status=200, body=b'[{"RA": "Crossref"}]')
        if url.startswith("https://doi.org/"):
            doi = urllib.parse.unquote(url.removeprefix("https://doi.org/"))
            title = TITLES.get(doi)
            if title is None:
                return FetchResponse(status=404)
            if "csl+json" in accept:
                body = {
                    "DOI": doi,
                    "title": title,
                    "issued": {"date-parts": [[2021]]},
                    "type": "journal-article",
                }
                return FetchResponse(status=200, body=json.dumps(body).encode())
            if "x-bibtex" in accept:
                bib = (
                    f"@article{{k,\n  title = {{{title}}},\n"
                    f"  year = {{2021}},\n  doi = {{{doi}}},\n}}\n"
                )
                return FetchResponse(status=200, body=bib.encode())
        raise AssertionError(f"unexpected url: {url}")


class FixtureExpanderLLM:
    async def ainvoke(self, messages):
        query = str(messages[-1][1])

        class R:
            content = json.dumps(EXPANSION_FIXTURE.get(query, []))

        return R()


class FixtureWebTool:
    async def ainvoke(self, args):
        return WEB_FIXTURE.get(args.get("query", ""), "")


def _coordinator(tmp_path):
    hub = CitationProviderHub(
        env={"OPENALEX_API_KEY": "fixture-key"}, fetcher=BenchmarkFetcher()
    )
    return CitationCoordinator(
        hub,
        web_tools={"get-web-search-summaries": FixtureWebTool()},
        llm_factory=lambda: FixtureExpanderLLM(),
        output_dir=tmp_path / "cite",
    )


def _top10_dois(coordinator):
    page, _ = coordinator.list_candidates(1)
    return [c.doi for c in page]


def test_doi_and_exact_title_cases_hit_top10_on_first_search(tmp_path):
    coordinator = _coordinator(tmp_path)
    for doi in DOI_CASES:
        outcome = asyncio.run(coordinator.search(doi))
        assert outcome.candidates[0].doi == doi  # direct lookup: rank 1
    for title, doi in EXACT_TITLE_CASES:
        asyncio.run(coordinator.search(title))
        top10 = _top10_dois(coordinator)
        assert doi in top10, f"exact-title case {title!r} missed top 10"
        # Exact-title tie-break puts the expected work first.
        assert top10[0] == doi


def test_topic_recall_at_10_beats_frozen_baseline(tmp_path):
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    coordinator = _coordinator(tmp_path)
    asyncio.run(coordinator.search(TOPIC_QUERY))
    examined = set(_top10_dois(coordinator))
    # /citation more keeps existing candidate order and appends; the metric
    # counts what the user examines: first-page top 10 plus the appended
    # web candidates.
    appended = asyncio.run(coordinator.more())
    examined |= {c.doi for c in appended.candidates if c.doi}

    recall = len(examined & set(RELEVANT)) / len(RELEVANT)
    assert recall > baseline["topic_recall_at_10"], (
        f"Recall@10 {recall:.3f} did not beat frozen baseline "
        f"{baseline['topic_recall_at_10']}"
    )
    # Deterministic on the fixed fixtures: 5 of 6 relevant works examined.
    assert recall == len(examined & set(RELEVANT)) / 6
    assert len(examined & set(RELEVANT)) == 5


def test_gold_corpus_produces_zero_false_saves(tmp_path):
    coordinator = _coordinator(tmp_path)

    # Intentional true save: exact-title case confirmed to its expected DOI.
    title, doi = EXACT_TITLE_CASES[0]
    asyncio.run(coordinator.search(title))
    target = next(
        c for c in coordinator.list_candidates(1)[0] if c.doi == doi
    )
    select = asyncio.run(coordinator.select(target.candidate_id))
    match = next(m for m in select.matches if m.canonical_doi == doi)
    confirmed = asyncio.run(coordinator.confirm(match.match_id))
    assert confirmed.status == "confirmed"

    # No-DOI candidate: viewable but unsaveable.
    asyncio.run(coordinator.search(TOPIC_QUERY))
    no_doi_result = asyncio.run(coordinator.more("no such topic"))
    assert no_doi_result.candidates == []

    # A DOI that stops resolving fails the confirm and writes nothing.
    asyncio.run(coordinator.search(TOPIC_QUERY))
    victim = next(
        c for c in coordinator.list_candidates(1)[0] if c.doi == RELEVANT[0]
    )
    select = asyncio.run(coordinator.select(victim.candidate_id))
    TITLES_BACKUP = TITLES.pop(RELEVANT[0])
    try:
        failed = asyncio.run(coordinator.confirm(select.matches[0].match_id))
    finally:
        TITLES[RELEVANT[0]] = TITLES_BACKUP
    assert failed.status in {"provider_failed", "verification_failed"}
    assert failed.accepted_doi is None

    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1  # exactly the one intentional save
    saved_sidecar = json.loads(
        next((tmp_path / "cite").glob("*/citation.json")).read_text(
            encoding="utf-8"
        )
    )
    assert saved_sidecar["doi"] == doi  # never a noise/wrong DOI
