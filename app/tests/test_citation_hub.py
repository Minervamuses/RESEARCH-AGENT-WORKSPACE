import pytest

from skills.citation.hub import CitationProviderHub


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
