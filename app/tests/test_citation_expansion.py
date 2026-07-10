"""Query expansion: lazy build, two-query cap, strings-only contract."""

import asyncio

from skills.citation.expansion import MAX_EXPANSIONS, QueryExpander, parse_expansions


class _StubLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)

        class R:
            pass

        response = R()
        response.content = self.content
        return response


def test_expander_is_lazy_and_caches_factory_failure():
    attempts = []

    def factory():
        attempts.append(1)
        raise RuntimeError("no key")

    expander = QueryExpander(factory)
    assert attempts == []  # nothing at construction
    assert asyncio.run(expander.expand("q")) == []
    assert asyncio.run(expander.expand("q")) == []
    assert len(attempts) == 1  # failure cached, not retried per call


def test_expand_returns_at_most_two_new_queries():
    llm = _StubLLM('["dense retrieval", "BM25 efficiency", "third one"]')
    expander = QueryExpander(lambda: llm)
    result = asyncio.run(expander.expand("retrieval efficiency"))
    assert result == ["dense retrieval", "BM25 efficiency"]
    assert MAX_EXPANSIONS == 2


def test_expand_drops_original_query_and_non_strings():
    raw = '["Retrieval Efficiency", 42, {"q": "x"}, "  ", "learned sparse retrieval"]'
    assert parse_expansions(raw, original_query="retrieval efficiency") == [
        "learned sparse retrieval"
    ]


def test_llm_metadata_or_scores_are_rejected_wholesale():
    # Anything that is not a JSON array of strings expands to nothing — the
    # LLM cannot smuggle metadata or relevance scores into discovery.
    assert parse_expansions('{"queries": ["a"], "relevance": 0.9}', original_query="q") == []
    assert parse_expansions("plain prose answer", original_query="q") == []
    assert parse_expansions("", original_query="q") == []


def test_code_fenced_json_is_accepted():
    raw = '```json\n["query one"]\n```'
    assert parse_expansions(raw, original_query="q") == ["query one"]


def test_llm_call_failure_degrades_to_no_expansions():
    class Boom:
        async def ainvoke(self, messages):
            raise RuntimeError("api down")

    expander = QueryExpander(lambda: Boom())
    assert asyncio.run(expander.expand("q")) == []


def test_timeout_degrades_to_no_expansions():
    class Slow:
        async def ainvoke(self, messages):
            await asyncio.sleep(5)

    expander = QueryExpander(lambda: Slow(), timeout=0.01)
    assert asyncio.run(expander.expand("q")) == []
