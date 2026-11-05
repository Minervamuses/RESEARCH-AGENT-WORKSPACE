"""Compare citekeys.find_citations with Pandoc's Cite nodes (key sequence).

Usage: python crosscheck.py <file.md> [...]; prints counts and differences
only (never document text).
"""
import json
import subprocess
import sys

from skills.citation.citekeys import keys_in

PANDOC = "/home/minervamuses/miniconda3/envs/app/bin/pandoc"


def pandoc_keys(text):
    out = subprocess.run([PANDOC, "-f", "markdown", "-t", "json"], input=text,
                         capture_output=True, text=True, check=True).stdout
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

    walk(json.loads(out)["blocks"])
    return keys


for path in sys.argv[1:]:
    text = open(path, encoding="utf-8").read()
    ours, theirs = keys_in(text, "markdown"), pandoc_keys(text)
    status = "MATCH" if ours == theirs else "DIFF"
    print(json.dumps({"file": path.rsplit("/", 1)[-1], "status": status,
                      "parser_uses": len(ours), "pandoc_uses": len(theirs),
                      "distinct_keys": len(set(theirs)),
                      "first_appearance_match": list(dict.fromkeys(ours)) == list(dict.fromkeys(theirs)),
                      "only_parser": sorted(set(ours) - set(theirs)),
                      "only_pandoc": sorted(set(theirs) - set(ours))}, ensure_ascii=False))
    if ours != theirs and len(ours) == len(theirs):
        print("  first sequence mismatch at", next(i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b))
