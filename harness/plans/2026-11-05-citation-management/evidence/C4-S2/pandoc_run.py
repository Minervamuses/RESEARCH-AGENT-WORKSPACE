"""Render corpus.json with Pandoc citeproc. Usage: python -I pandoc_run.py corpus.json styles_dir > out.json"""
import json, subprocess, sys, tempfile, pathlib

PANDOC = "/home/minervamuses/miniconda3/envs/app/bin/pandoc"
STYLES = ["apa", "modern-language-association", "ieee", "chicago-author-date"]
corpus = json.load(open(sys.argv[1], encoding="utf-8"))
styles_dir = pathlib.Path(sys.argv[2]).resolve()


def cluster_md(cluster):
    parts = []
    for x in cluster:
        text = ("-" if x.get("suppress-author") else "") + "@" + x["id"]
        if x.get("locator"):
            text += ", " + {"page": "p.", "chapter": "chap."}[x["label"]] + " " + x["locator"]
        parts.append(text)
    return "[" + "; ".join(parts) + "]"


def walk_inlines(node, out):
    if isinstance(node, dict):
        if node.get("t") == "Cite":
            out.append(node["c"][1])
            return
        for value in node.values():
            walk_inlines(value, out)
    elif isinstance(node, list):
        for value in node:
            walk_inlines(value, out)


def to_plain(blocks_or_inlines, kind):
    doc = {"pandoc-api-version": API, "meta": {}, "blocks": blocks_or_inlines if kind == "blocks" else [{"t": "Plain", "c": blocks_or_inlines}]}
    return subprocess.run([PANDOC, "-f", "json", "-t", "plain", "--wrap=none"], input=json.dumps(doc), capture_output=True, text=True, check=True).stdout.strip()


API = json.loads(subprocess.run([PANDOC, "-t", "json"], input="x", capture_output=True, text=True).stdout)["pandoc-api-version"]
out = {}
for style in STYLES:
    out[style] = {}
    for case in corpus["cases"]:
        with tempfile.TemporaryDirectory() as tmp:
            refs = pathlib.Path(tmp, "refs.json")
            refs.write_text(json.dumps(case["items"], ensure_ascii=False))
            md = "\n\n".join(cluster_md(c) for c in case["clusters"]) + "\n\n::: {#refs}\n:::\n"
            ast = json.loads(subprocess.run(
                [PANDOC, "--citeproc", "--bibliography", str(refs), "--csl", str(styles_dir / f"{style}.csl"), "-f", "markdown", "-t", "json"],
                input=md, capture_output=True, text=True, check=True).stdout)
        cites = []
        walk_inlines(ast["blocks"], cites)
        refs_div = next(b for b in ast["blocks"] if b["t"] == "Div" and b["c"][0][0] == "refs")
        entries = [to_plain(entry["c"][1], "blocks") for entry in refs_div["c"][1]]
        out[style][case["id"]] = {"citations": [to_plain(c, "inlines") for c in cites], "bibliography": entries}
print(json.dumps(out, ensure_ascii=False, indent=1))
