import pytest

from skills.citation.hub import CitationProviderHub

pytestmark = pytest.mark.usefixtures("no_citation_backoff")


def test_hub_starts_inside_public_provider_rate_limits():
    hub = CitationProviderHub(env={})

    assert hub.crossref_limiter.max_concurrency == 1
    assert hub.crossref_limiter.min_interval == pytest.approx(1.0)
    assert hub.datacite_limiter.max_concurrency == 2
    assert hub.datacite_limiter.min_interval == pytest.approx(0.6)
    assert hub.crossref._mailto is None  # noqa: SLF001 - configuration contract
    assert hub.datacite._mailto is None  # noqa: SLF001 - configuration contract


def test_hub_uses_contact_identified_provider_limits():
    hub = CitationProviderHub(
        env={
            "CROSSREF_MAILTO": "crossref@example.org",
            "DATACITE_MAILTO": "datacite@example.org",
        }
    )

    assert hub.crossref_limiter.max_concurrency == 3
    assert hub.crossref_limiter.min_interval == pytest.approx(1.0 / 3.0)
    assert hub.datacite_limiter.min_interval == pytest.approx(0.3)
    assert hub.crossref._mailto == "crossref@example.org"  # noqa: SLF001
    assert hub.datacite._mailto == "datacite@example.org"  # noqa: SLF001


def _hub_with_transport(handler) -> CitationProviderHub:
    import httpx

    hub = CitationProviderHub(env={})
    hub._http_client = httpx.AsyncClient(  # noqa: SLF001 - transport seam
        transport=httpx.MockTransport(handler)
    )
    for limiter in (hub.crossref_limiter, hub.datacite_limiter, hub.doi_org_limiter):
        limiter.update(min_interval=0.0)  # retries still enter the limiter
    return hub


@pytest.mark.parametrize(
    ("error_type", "retryable"),
    [
        ("ConnectError", True),
        ("ReadError", True),
        ("RemoteProtocolError", True),
        ("TooManyRedirects", False),
        ("DecodingError", False),
    ],
)
def test_httpx_transport_failures_become_provider_network_errors(
    error_type, retryable,
):
    import asyncio

    import httpx

    from skills.citation.providers.net import ProviderError, ProviderNetworkError

    def handler(request):
        raise getattr(httpx, error_type)("simulated failure", request=request)

    async def scenario():
        hub = _hub_with_transport(handler)
        try:
            await hub.doi_org.fetch_structured("10.1234/x")
        finally:
            await hub.aclose()

    with pytest.raises(ProviderNetworkError) as exc:
        asyncio.run(scenario())
    assert isinstance(exc.value, ProviderError)
    assert exc.value.provider == "doi.org"
    assert exc.value.exc_type == error_type
    assert exc.value.retryable is retryable


def test_bounded_datacite_fetch_maps_transport_failures():
    import asyncio

    import httpx

    from skills.citation.providers.base import BibliographicQuery
    from skills.citation.providers.net import ProviderNetworkError

    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    async def scenario():
        hub = _hub_with_transport(handler)
        try:
            await hub.datacite.search_work(BibliographicQuery(title="Paper A"))
        finally:
            await hub.aclose()

    with pytest.raises(ProviderNetworkError) as exc:
        asyncio.run(scenario())
    assert exc.value.provider == "datacite"
    assert exc.value.exc_type == "ConnectError"


def test_httpx_timeout_keeps_provider_timeout_route():
    import asyncio

    import httpx

    from skills.citation.providers.net import ProviderTimeout

    def handler(request):
        raise httpx.ReadTimeout("read timed out", request=request)

    async def scenario():
        hub = _hub_with_transport(handler)
        try:
            await hub.doi_org.fetch_bibtex("10.1234/x")
        finally:
            await hub.aclose()

    with pytest.raises(ProviderTimeout):
        asyncio.run(scenario())


def test_search_survives_one_provider_connection_failure(tmp_path):
    import asyncio
    import json

    import httpx

    from skills.citation.service import CitationService

    def handler(request):
        if request.url.host == "api.crossref.org":
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"data": [{
            "id": "10.5281/zenodo.1",
            "attributes": {
                "doi": "10.5281/zenodo.1",
                "titles": [{"title": "Dataset A"}],
                "publicationYear": 2022,
                "types": {"resourceTypeGeneral": "Dataset"},
            },
        }]})

    async def scenario():
        hub = _hub_with_transport(handler)
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            return await service.search("dataset a")
        finally:
            await hub.aclose()

    records, states = asyncio.run(scenario())
    assert [record.doi for record in records] == ["10.5281/zenodo.1"]
    assert states[0].startswith("crossref:")
    assert states[0] != "crossref:ok"
    assert json.dumps(states)  # plain strings for the tool payload


_DATACITE_RECORD = {"data": [{
    "id": "10.5281/zenodo.1",
    "attributes": {
        "doi": "10.5281/zenodo.1", "titles": [{"title": "Dataset A"}], "publicationYear": 2022,
        "types": {"resourceTypeGeneral": "Dataset"},
    },
}]}
_CROSSREF_RECORD = {"message": {"items": [{
    "DOI": "10.1234/paper-a", "title": ["Paper A"], "issued": {"date-parts": [[2021]]},
    "type": "journal-article", "score": 10.0,
}]}}


def _failing_provider_hub(calls, *, crossref=None, datacite=None):
    """Offline hub where each provider either answers or fails the same way every time."""
    import httpx

    def handler(request):
        host = request.url.host
        calls.append(host)
        behaviour = crossref if host == "api.crossref.org" else datacite
        if behaviour == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        if isinstance(behaviour, int):
            return httpx.Response(behaviour, json={})
        return httpx.Response(200, json=_CROSSREF_RECORD if host == "api.crossref.org" else _DATACITE_RECORD)

    return _hub_with_transport(handler)


@pytest.mark.parametrize(("datacite", "first_state", "attempts"), [
    ("timeout", "datacite:timeout", 2),
    (503, "datacite:server_error(503)", 3),
    (429, "datacite:rate_limited", 3),
])
def test_a_provider_that_exhausted_retries_is_skipped_for_the_rest_of_the_task(
    tmp_path, no_citation_backoff, datacite, first_state, attempts,
):
    import asyncio

    from skills.citation.service import CitationService
    from skills.citation.tool import create_citation_workflow_tool

    calls = []

    async def scenario():
        hub = _failing_provider_hub(calls, datacite=datacite)
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            first = await service.search("first topic")
            first_waits = list(no_citation_backoff)
            tool = create_citation_workflow_tool(service_getter=lambda: service)
            second_text = await tool.ainvoke({"action": "search", "query": "second topic"})
            second_waits = no_citation_backoff[len(first_waits):]
            next_task = await CitationService(hub, output_dir=tmp_path / "cite").search("third topic")
            return first, first_waits, second_text, second_waits, next_task
        finally:
            await hub.aclose()

    (records, states), first_waits, second_text, second_waits, next_task = asyncio.run(scenario())
    assert [record.doi for record in records] == ["10.1234/paper-a"]
    assert states == ["crossref:ok", first_state]
    assert len(first_waits) == attempts - 1
    # The same task's next query neither calls nor waits for the failed provider again.
    assert calls.count("api.datacite.org") == attempts + attempts  # first task + the next task only
    assert second_waits == []
    assert "1. Paper A" in second_text and "   DOI: 10.1234/paper-a" in second_text
    assert "datacite:skipped(" + first_state.split(":", 1)[1].split("(", 1)[0] + " earlier in this task)" in second_text
    assert "Search incomplete: some providers failed" in second_text
    # A new task (the next /citation turn) tries the provider again.
    assert next_task[1] == ["crossref:ok", first_state]


@pytest.mark.parametrize("datacite", [404, "ok"])
def test_deterministic_errors_and_successes_do_not_skip_the_provider(tmp_path, datacite):
    import asyncio

    from skills.citation.service import CitationService

    calls = []

    async def scenario():
        hub = _failing_provider_hub(calls, datacite=None if datacite == "ok" else datacite)
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            return [await service.search(query) for query in ("first topic", "second topic")]
        finally:
            await hub.aclose()

    results = asyncio.run(scenario())
    expected = "datacite:ok" if datacite == "ok" else "datacite:http_error(404)"
    assert [states[1] for _records, states in results] == [expected, expected]
    assert calls.count("api.datacite.org") == 2


def test_all_providers_failing_then_skipped_is_reported_as_failed_not_zero_hits(tmp_path):
    import asyncio

    from skills.citation.service import CitationService
    from skills.citation.tool import create_citation_workflow_tool

    calls = []

    async def scenario():
        hub = _failing_provider_hub(calls, crossref="timeout", datacite="timeout")
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            tool = create_citation_workflow_tool(service_getter=lambda: service)
            first = await tool.ainvoke({"action": "search", "query": "first topic"})
            second = await tool.ainvoke({"action": "search", "query": "second topic"})
            return first, second
        finally:
            await hub.aclose()

    first, second = asyncio.run(scenario())
    assert first.startswith("Search failed: no provider answered successfully")
    assert second.startswith("Search failed: no provider answered successfully (crossref:skipped(timeout")
    assert "not evidence that the work does not exist" in second
    assert len(calls) == 4  # two attempts per provider, only during the first query


def test_cancelled_search_records_no_provider_failure(tmp_path):
    import asyncio

    import httpx

    from skills.citation.service import CitationService

    entered = None

    async def scenario():
        nonlocal entered
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        hub = _hub_with_transport(handler)
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            task = asyncio.create_task(service.search("topic"))
            await asyncio.wait_for(entered.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            return service._failed_search_providers  # noqa: SLF001 - turn-scoped state
        finally:
            await hub.aclose()

    assert asyncio.run(scenario()) == {}
