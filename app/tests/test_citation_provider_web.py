"""Web MCP adapter: parsing real-format fixtures, URL normalization, errors."""

import asyncio

import pytest

from citation.providers.net import ProviderError, ProviderTimeout
from citation.providers.web import (
    WebSearchProvider,
    normalize_url,
    parse_search_text,
    unwrap_redirect_url,
)

# Shape taken from real mrkrsl/web-search-mcp v0.3.2 output.
FIXTURE_TEXT = """Search summaries:

**1. arXiv arxiv.org › abs  › 1706.03762   [1706.03762] Attention Is All You Need**
URL: https://arxiv.org/abs/1706.03762
Description: DOI: 10.48550/arXiv.1706.03762

---

**2. Google Scholar**
URL: https://scholar.google.com/scholar_lookup?title=Attention+is+all+you+need&amp=&author=A.+Vaswani&amp=&publication_year=2017&amp=&doi=10.48550/arXiv.1706.03762
Description: No description available

---

**3. Ashish Vaswani**
URL: https://scholar.google.com/citations?user=oR9sCGYAAAAJ&hl=en
Description: No description available

---

**4. Some survey without doi**
URL: https://Example.ORG/Papers/Survey?b=2&a=1
Description: A survey of transformer models published in 2021.
"""


def test_parse_extracts_titles_dois_and_scholar_identity_metadata():
    records = parse_search_text(FIXTURE_TEXT)
    assert [r.rank for r in records] == [0, 1, 2]

    arxiv = records[0]
    assert arxiv.title == "Attention Is All You Need"
    assert arxiv.doi == "10.48550/arxiv.1706.03762"

    scholar = records[1]
    # Generic "Google Scholar" label replaced by the lookup title param.
    assert scholar.title == "Attention is all you need"
    assert scholar.doi == "10.48550/arxiv.1706.03762"
    assert scholar.year == 2017
    assert scholar.authors == ["A. Vaswani"]
    # Scholar identity params survive normalization (sorted, not stripped).
    assert "title=Attention+is+all+you+need" in scholar.url
    assert "author=A.+Vaswani" in scholar.url

    # Author profile page filtered; DOI-less survey kept with year guess.
    survey = records[2]
    assert survey.doi is None
    assert survey.year == 2021


def test_normalize_url_lowercases_scheme_host_and_sorts_query_only():
    assert (
        normalize_url("HTTPS://Example.ORG/Papers/Survey?b=2&a=1")
        == "https://example.org/Papers/Survey?a=1&b=2"
    )
    # Path case is preserved; empty values kept.
    assert normalize_url("https://x.org/A/B?z=&y=1") == "https://x.org/A/B?y=1&z="
    assert normalize_url(None) is None
    assert normalize_url("not a url") == "not a url"


def test_normalize_url_never_discards_the_query():
    url = (
        "https://scholar.google.com/scholar_lookup?title=T&author=A"
        "&publication_year=2017&doi=10.1/x"
    )
    normalized = normalize_url(url)
    for param in ("title=T", "author=A", "publication_year=2017"):
        assert param in normalized


def test_unwrap_bing_redirect():
    import base64
    target = "https://arxiv.org/abs/1706.03762"
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    wrapped = f"https://www.bing.com/ck/a?!&&p=x&u=a1{encoded}&ntb=1"
    assert unwrap_redirect_url(wrapped) == target
    assert unwrap_redirect_url("https://example.org/x") == "https://example.org/x"


class _StubTool:
    def __init__(self, result=None, error=None, delay=0.0):
        self.result = result
        self.error = error
        self.delay = delay
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


def test_search_uses_summaries_tool_and_caps_rows():
    tool = _StubTool(result=FIXTURE_TEXT)
    provider = WebSearchProvider({"get-web-search-summaries": tool})
    assert provider.available
    records = asyncio.run(provider.search("attention", rows=99))
    assert tool.calls == [{"query": "attention", "limit": 20}]
    assert len(records) == 3


def test_search_without_tool_raises_provider_error():
    provider = WebSearchProvider({})
    assert not provider.available
    with pytest.raises(ProviderError):
        asyncio.run(provider.search("q"))


def test_search_timeout_and_tool_failure_are_distinct():
    slow = WebSearchProvider(
        {"get-web-search-summaries": _StubTool(result="", delay=5)}, timeout=0.01
    )
    with pytest.raises(ProviderTimeout):
        asyncio.run(slow.search("q"))

    broken = WebSearchProvider(
        {"get-web-search-summaries": _StubTool(error=RuntimeError("boom"))}
    )
    with pytest.raises(ProviderError) as exc:
        asyncio.run(broken.search("q"))
    assert not isinstance(exc.value, ProviderTimeout)


def test_parse_dedupes_by_normalized_url():
    text = (
        "**1. Paper**\nURL: https://EXAMPLE.org/p?b=2&a=1\nDescription: x\n\n"
        "**2. Paper again**\nURL: https://example.org/p?a=1&b=2\nDescription: y\n"
    )
    records = parse_search_text(text)
    assert len(records) == 1
