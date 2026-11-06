"""Seeded differential test: citekeys must find the same citations as Pandoc.

Documents are assembled from fragments covering every construct the parser
treats specially (code, comments, math, autolinks, HTML, links and their
targets/titles/attributes, reference definitions, footnotes, example lists,
escapes, e-mail addresses, braced keys, punctuation). Two known, documented
count differences are not generated: a footnote referenced more than once and
an image alone in a paragraph (Pandoc duplicates their citations).
"""

import json
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from skills.citation import csl_render
from skills.citation.citekeys import keys_in

PANDOC = csl_render.find_pandoc()
pytestmark = pytest.mark.skipif(PANDOC is None, reason="Pandoc is not installed")

INLINE = [
    "[@{k}]", "[see @{k}, p. 3; -@{k2}]", "@{k} says", "mail jane@{k}.org", "`@{k}`", "<!-- @{k} -->",
    "$x @{k}$", "\\@{k}", '[x](https://x.org/@{k} "t @{k2}")', "[@{k}](https://y.org/@{k2})",
    "[see @{k}](<https://z.org/a b/@{k2}>)", '<span title="@{k}">@{k2}</span>', "@{{{k}.v}}", "見@{k} 與 @{k2}。",
    '[span @{k}]{{.c key="@{k2}"}}', "https://x.org/@{k}", "<https://x.org/@{k}>", "word,@{k}", "(@{k}) mid",
    "[x][{k}ref]", "@{k}:sub.", "[unclosed](https://x.org/@{k}", "text](https://x.org/@{k})", "😀 @{k}",
]
BLOCK = [
    '[{k}ref]: https://x.org/@{k2} "t @{k}"', "[@{k}]: https://x.org/@{k2}", "[-@{k}]: https://x.org",
    "```\n@{k}\n```", "    @{k} indented after a blank line", "- item @{k}\n    continued @{k2}", "(@{k}) example item",
    "> quote @{k}", "| a | @{k} |\n|---|---|\n| @{k2} | x |",
]
FOOTNOTES = ["[@{k}]", "https://x.org/@{k}", "[x](https://x.org/@{k})", "see @{k} and @{k2}"]


def _document(rng, index):
    parts, notes = [], []
    for n in range(rng.randint(2, 6)):
        k, k2 = f"d{index}n{n}a", f"d{index}n{n}b"
        roll = rng.random()
        if roll < 0.6:
            words = [rng.choice(INLINE).format(k=k, k2=k2) for _ in range(rng.randint(1, 3))]
            parts.append("Text " + " and ".join(words) + ".")
        elif roll < 0.85:
            parts.append(rng.choice(BLOCK).format(k=k, k2=k2))
        else:
            label = f"f{index}n{n}"
            parts.append(f"Claim[^{label}] here.")
            notes.append(f"[^{label}]: " + rng.choice(FOOTNOTES).format(k=k, k2=k2))
    return "\n\n".join(parts + notes) + "\n"


def _pandoc_keys(text):
    ast = json.loads(subprocess.run([PANDOC, "-f", "markdown", "-t", "json"], input=text,
                                    capture_output=True, text=True, check=True).stdout)
    keys = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Cite":
                keys.extend(c["citationId"] for c in node["c"][0])
                walk(node["c"][1])
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ast["blocks"])
    return keys


def test_parser_matches_pandoc_on_generated_documents():
    rng = random.Random(20261106)
    documents = [_document(rng, index) for index in range(240)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        expected = list(pool.map(_pandoc_keys, documents))
    mismatches = [
        (doc, keys_in(doc, "markdown"), want)
        for doc, want in zip(documents, expected)
        if keys_in(doc, "markdown") != want
    ]
    assert not mismatches, f"{len(mismatches)} of {len(documents)} differ; first: {mismatches[:2]}"
