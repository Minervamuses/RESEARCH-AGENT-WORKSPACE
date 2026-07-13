import json

from skills.citation.providers.net import FetchResponse

DOI_A = "10.1234/paper-a"
DOI_B = "10.1234/paper-b"
CSL = {
    DOI_A: {"DOI": DOI_A, "title": "Paper A", "author": [{"given": "Ada", "family": "Lovelace"}], "issued": {"date-parts": [[2021]]}, "container-title": "Journal A", "type": "journal-article"},
    DOI_B: {"DOI": DOI_B, "title": "Paper B", "author": [{"given": "Bob", "family": "Builder"}], "issued": {"date-parts": [[2020]]}, "type": "journal-article"},
}
BIBTEX = {
    DOI_A: f"@article{{a, title={{Paper A}}, author={{Lovelace, Ada}}, year={{2021}}, doi={{{DOI_A}}}}}\n",
    DOI_B: "@article{b, title={Paper B}, author={Builder, Bob}, year={2020}}\n",
}
CROSSREF_ITEMS = [
    {"DOI": DOI_A, "title": ["Paper A"], "author": [{"given": "Ada", "family": "Lovelace"}], "issued": {"date-parts": [[2021]]}, "container-title": ["Journal A"], "type": "journal-article", "score": 10.0},
    {"DOI": DOI_B, "title": ["Paper B"], "issued": {"date-parts": [[2020]]}, "type": "journal-article", "score": 8.0},
]


class RoutingFetcher:
    def __init__(self):
        self.calls = []

    async def __call__(self, url, headers):
        accept = headers.get("Accept", "")
        self.calls.append((url, accept))
        if "api.crossref.org" in url:
            return FetchResponse(200, body=json.dumps({"message": {"items": CROSSREF_ITEMS}}).encode())
        if "api.datacite.org" in url:
            return FetchResponse(200, body=b'{"data": []}')
        if url.startswith("https://doi.org/"):
            doi = url.removeprefix("https://doi.org/")
            if "csl+json" in accept:
                return FetchResponse(200, body=json.dumps(CSL[doi]).encode()) if doi in CSL else FetchResponse(404)
            if "x-bibtex" in accept:
                return FetchResponse(200, body=BIBTEX[doi].encode()) if doi in BIBTEX else FetchResponse(404)
        raise AssertionError(f"unexpected url: {url}")
