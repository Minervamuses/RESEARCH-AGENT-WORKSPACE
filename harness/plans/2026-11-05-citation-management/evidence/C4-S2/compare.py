"""Compare out-citeproc-js.json with out-pandoc.json; write comparison.json + summary.md."""
import json
import re
import unicodedata

CORE = {"names": "作者清單/et al.", "disambiguation": "消歧", "ordering": "排序/編號", "locator": "locator"}
OTHER = {"case": "大小寫", "punctuation": "標點", "other": "其他"}
corpus = {c["id"]: c for c in json.load(open("corpus.json", encoding="utf-8"))["cases"]}
js = json.load(open("out-citeproc-js.json", encoding="utf-8"))
pd = json.load(open("out-pandoc.json", encoding="utf-8"))


def norm(text):
    text = unicodedata.normalize("NFC", text).replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def classify(case, a, b):
    """Category of a difference: punctuation-only when letters/digits agree."""
    strip = lambda s: re.sub(r"[\W_]+", "", s)
    if strip(a) == strip(b):
        return "punctuation"
    if strip(a).casefold() == strip(b).casefold():
        return "case"
    return corpus[case]["category"]


rows = []
for style in js:
    for case in corpus:
        a, b = js[style][case], pd[style][case]
        diffs = []
        for part in ("citations", "bibliography"):
            for index, (x, y) in enumerate(zip(a[part], b[part])):
                if norm(x) != norm(y):
                    diffs.append({"part": part, "index": index, "citeproc_js": x, "pandoc": y, "category": classify(case, norm(x), norm(y))})
            if len(a[part]) != len(b[part]):
                diffs.append({"part": part, "index": None, "citeproc_js": len(a[part]), "pandoc": len(b[part]), "category": corpus[case]["category"]})
        rows.append({"style": style, "case": case, "match": not diffs, "diffs": diffs})
json.dump(rows, open("comparison.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

core_mismatches = sum(1 for r in rows for d in r["diffs"] if d["category"] in CORE)
lines = ["# C4-S2 Pandoc vs citeproc-js", "",
         "- Pandoc 3.13 (citeproc Haskell library inside pandoc) vs citeproc-js 2.4.63 (npm `citeproc`), en-US locale from citation-style-language/locales `8bef426`.",
         "- Styles: the four bundled CSL files (styles commit `205bf7b`). Corpus: `corpus.json` (%d cases). Strings compared after NFC and whitespace normalization; Pandoc output is plain text (italics dropped), citeproc-js output format `text`." % len(corpus),
         "- Core categories: " + ", ".join(CORE.values()) + ".", "",
         "| case | category | " + " | ".join(js) + " |", "|---|---|" + "---|" * len(js)]
for case in corpus:
    cells = []
    for style in js:
        row = next(r for r in rows if r["style"] == style and r["case"] == case)
        cells.append("✓" if row["match"] else "✗ " + ", ".join(sorted({{**CORE, **OTHER}[d["category"]] for d in row["diffs"]})))
    lines.append(f"| {case} | {({**CORE, **OTHER})[corpus[case]['category']]} | " + " | ".join(cells) + " |")
total = len(rows)
matched = sum(r["match"] for r in rows)
lines += ["", f"- 一致：{matched}/{total} 組（樣式×案例）。", f"- **Pandoc 在核心類別的不一致數：{core_mismatches}**。", ""]
for r in rows:
    for d in r["diffs"]:
        lines += [f"## {r['style']} / {r['case']} ({d['part']} {d['index']}, {({**CORE, **OTHER})[d['category']]})", "",
                  f"- citeproc-js: `{d['citeproc_js']}`", f"- Pandoc: `{d['pandoc']}`", ""]
open("summary.md", "w", encoding="utf-8").write("\n".join(lines))
print(f"matched {matched}/{total}; core mismatches {core_mismatches}")
