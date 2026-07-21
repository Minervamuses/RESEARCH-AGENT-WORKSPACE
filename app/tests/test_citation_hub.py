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
