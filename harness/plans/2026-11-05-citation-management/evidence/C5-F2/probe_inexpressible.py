"""C5-F2: can a CSL style remove the 4 remaining Appendix 17 difference categories?

For each category, minimal styles isolate the CSL mechanisms that could
matter; each is rendered by Pandoc 3.13 and citeproc-js 2.4.63. Data
variants show what a change to the bibliography (not the style) would do.
Usage: python -I probe_inexpressible.py <evidence-dir> <citeproc-js dir> <locale.xml>
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PANDOC = "/home/minervamuses/miniconda3/envs/app/bin/pandoc"
NODE = "/home/minervamuses/miniconda3/envs/app/bin/node"
E, CPJS, LOCALE = (Path(arg) for arg in sys.argv[1:4])


def style(layout, style_attrs=""):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" {style_attrs}>
  <info><title>probe</title><id>probe</id><updated>2026-11-06T00:00:00+00:00</updated></info>
  <citation><layout><text variable="title"/></layout></citation>
  <bibliography><sort><key variable="title"/></sort><layout>{layout}</layout></bibliography>
</style>'''


def run(csl, items):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "s.csl").write_text(csl, encoding="utf-8")
        (tmp / "r.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        doc = "---\nnocite: '[@*]'\n---\n"
        plain = subprocess.run([PANDOC, "--citeproc", "--csl", str(tmp / "s.csl"), "--bibliography", str(tmp / "r.json"),
                                "-f", "markdown", "-t", "plain", "--wrap=none"], input=doc, capture_output=True, text=True, check=True).stdout
        pandoc = [line for line in plain.split("\n") if line.strip()]
        js = json.loads(subprocess.run([NODE, str(E / "cpjs_bib.js"), str(tmp / "s.csl"), str(tmp / "r.json"), str(LOCALE)],
                                       capture_output=True, text=True, check=True, env={**os.environ, "NODE_PATH": str(CPJS)}).stdout)
        return {"pandoc": pandoc, "citeproc_js": [text for _id, text in js]}


NAMES = '<names variable="author"><name {attrs}/></names>'
results = []


def probe(category, label, csl, items, expected):
    out = run(csl, items)
    results.append({"category": category, "variant": label, "expected": expected, **out,
                    "pandoc_matches": out["pandoc"] == expected, "citeproc_js_matches": out["citeproc_js"] == expected})


# A. Straight apostrophe -> typographic apostrophe
title_only = style('<text variable="title"/>')
items_a = [{"id": "a", "type": "article", "title": "Users' Views"}]
probe("A apostrophe", "style prints only the raw title", title_only, items_a, ["Users' Views"])
probe("A apostrophe", "quotes=false, no text-case", style('<text variable="title" quotes="false"/>'), items_a, ["Users' Views"])
probe("A apostrophe", "data: title already typographic", title_only, [{"id": "a", "type": "article", "title": "Users’ Views"}], ["Users' Views"])

# B. Hyphenated given name with a lower-case second part
items_b = [{"id": "b1", "type": "article", "title": "1", "author": [{"family": "Yih", "given": "Wen-tau"}]},
           {"id": "b2", "type": "article", "title": "2", "author": [{"family": "Godard", "given": "Jean-Luc"}]}]
expect_b = ["Yih, W.-t.", "Godard, J.-L."]
for label, attrs, style_attrs in [
    ("initialize-with '. ', initialize-with-hyphen true (default)", 'name-as-sort-order="all" initialize-with=". "', ""),
    ("initialize-with-hyphen false", 'name-as-sort-order="all" initialize-with=". "', 'initialize-with-hyphen="false"'),
    ("initialize-with '.' (no space)", 'name-as-sort-order="all" initialize-with="."', ""),
    ("initialize=false keeps given names", 'name-as-sort-order="all" initialize="false" initialize-with=". "', ""),
]:
    probe("B Wen-tau initials", label, style(NAMES.format(attrs=attrs), style_attrs), items_b, expect_b)
probe("B Wen-tau initials", "data: given already 'W.-t.'", style(NAMES.format(attrs='name-as-sort-order="all" initialize-with=". "')),
      [dict(items_b[0], author=[{"family": "Yih", "given": "W.-t."}]), items_b[1]], expect_b)

# C. Author list truncated in the data with a literal "et al." name
ten = [{"family": f"F{i}", "given": "A."} for i in range(1, 11)]
items_c = [{"id": "c1", "type": "article", "title": "1 truncated in source", "author": ten + [{"literal": "et al."}]},
           {"id": "c2", "type": "article", "title": "2 twelve real authors", "author": ten + [{"family": "F11", "given": "A."}, {"family": "F12", "given": "A."}]}]
full = ", ".join(f"F{i}, A." if i == 1 else f"A. F{i}" for i in range(1, 11))
expect_c = [f"{full}, et al.", f"{full}, A. F11, and A. F12"]
base = 'name-as-sort-order="first" initialize-with=". " delimiter=", "'
for label, attrs in [
    ("and=text, delimiter-precedes-last=always (the Appendix 17 style)", base + ' and="text" delimiter-precedes-last="always"'),
    ("no 'and'", base),
    ("et-al-min=11, et-al-use-first=10", base + ' and="text" delimiter-precedes-last="always" et-al-min="11" et-al-use-first="10" delimiter-precedes-et-al="always"'),
]:
    probe("C literal et al.", label, style(NAMES.format(attrs=attrs)), items_c, expect_c)

# D. Nickname in parentheses inside the given name
items_d = [{"id": "d", "type": "article", "title": "1", "author": [{"family": "Lee", "given": "Hao-Ping (Hank)"}]}]
expect_d = ["Lee, H.-P."]
for label, attrs in [
    ("initialize-with '. '", 'name-as-sort-order="all" initialize-with=". "'),
    ("initialize-with '.'", 'name-as-sort-order="all" initialize-with="."'),
]:
    probe("D nickname", label, style(NAMES.format(attrs=attrs)), items_d, expect_d)
probe("D nickname", "name-part given text-case=lowercase (only case changes exist)",
      style('<names variable="author"><name name-as-sort-order="all" initialize-with=". "><name-part name="given" text-case="lowercase"/></name></names>'),
      items_d, expect_d)
probe("D nickname", "data: nickname moved out of given", style(NAMES.format(attrs='name-as-sort-order="all" initialize-with=". "')),
      [dict(items_d[0], author=[{"family": "Lee", "given": "Hao-Ping"}])], expect_d)

(E / "probe-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for row in results:
    print(f"{row['category']:<20} | {row['variant'][:62]:<62} | pandoc={row['pandoc_matches']!s:<5} js={row['citeproc_js_matches']!s:<5} | {row['pandoc'][0][:60]}")
