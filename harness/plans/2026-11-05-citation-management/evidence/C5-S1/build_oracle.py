"""Build the Appendix 17 oracle from bime_word's proposal.docx.

Usage: python -I build_oracle.py <thesis-copy-dir> <out.json>
Reads proposal.md and proposal.docx copies (thesis HEAD). Writes only the
bibliography strings and, per citation group, its keys and the docx string
at that position; never the surrounding body text.
"""
import json
import re
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

PANDOC = "/home/minervamuses/miniconda3/envs/app/bin/pandoc"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root_dir = Path(sys.argv[1])


def norm(text):
    text = unicodedata.normalize("NFC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


doc = ET.fromstring(zipfile.ZipFile(root_dir / "proposal.docx").read("word/document.xml"))
paras = []
for p in doc.iter(W + "p"):
    style = p.find(f"{W}pPr/{W}pStyle")
    paras.append((style.get(W + "val") if style is not None else "", norm("".join(t.text or "" for t in p.iter(W + "t")))))
bibliography = [text for style, text in paras if style == "Bibliography"]
body = [text for style, text in paras if style != "Bibliography"]

ast = json.loads(subprocess.run([PANDOC, "-f", "markdown", "-t", "json"], input=(root_dir / "proposal.md").read_text(encoding="utf-8"),
                                capture_output=True, text=True, check=True).stdout)
API = ast["pandoc-api-version"]
SENT = ""
groups = []  # (keys, mode)


def mark(node):
    if isinstance(node, list):
        return [mark(x) for x in node]
    if isinstance(node, dict):
        if node.get("t") == "Cite":
            index = len(groups)
            citations = node["c"][0]
            groups.append({
                "keys": [c["citationId"] for c in citations],
                "modes": [c["citationMode"]["t"] for c in citations],
                "source": norm("".join(x.get("c", " ") if x.get("t") == "Str" else " " for x in node["c"][1])),
            })
            return {"t": "Str", "c": f"{SENT}{index}{SENT}"}
        return {k: mark(v) for k, v in node.items()}
    return node


blocks = mark(ast["blocks"])
plain = subprocess.run([PANDOC, "-f", "json", "-t", "plain", "--wrap=none"], input=json.dumps({"pandoc-api-version": API, "meta": {}, "blocks": blocks}),
                       capture_output=True, text=True, check=True).stdout
results = {}
in_todo = set()


def drop_todo(line):
    """bime_word leaves [TODO: ...] notes out of the docx; drop them here too."""
    while True:
        start = line.find("[TODO:")
        if start < 0:
            return line
        depth, end = 0, None
        for pos in range(start, len(line)):
            if line[pos] == "[":
                depth += 1
            elif line[pos] == "]":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        if end is None:
            return line
        for index in re.findall(SENT + r"(\d+)" + SENT, line[start:end]):
            in_todo.add(int(index))
        line = (line[:start].rstrip() + " " + line[end + 1:].lstrip()).strip()


for line in plain.split("\n"):
    if SENT not in line:
        continue
    line = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", norm(drop_todo(line)))
    if SENT not in line:
        continue
    parts = re.split(SENT + r"(\d+)" + SENT, line)
    literals, indices = parts[0::2], [int(x) for x in parts[1::2]]
    pattern = "".join(re.escape(lit) + ("(.*?)" if i < len(indices) else "") for i, lit in enumerate(literals))
    found = None
    for text in body:
        match = re.fullmatch(pattern, text) or re.search(pattern if literals[0] and literals[-1] else pattern, text)
        if match and all(g is not None for g in match.groups()):
            found = match
            break
    for position, index in enumerate(indices):
        results[index] = found.group(position + 1).strip() if found else None

citations = []
for index, group in enumerate(groups):
    citations.append({
        "index": index, "keys": group["keys"], "modes": group["modes"],
        "docx": results.get(index),
        "omitted_in_docx": "todo_note" if index in in_todo else None,
    })
oracle = {
    "source": "thesis repo HEAD proposal.docx (bime_word) + proposal.md",
    "bibliography": bibliography,
    "citations": citations,
    "counts": {
        "bibliography_entries": len(bibliography),
        "citation_groups": len(groups),
        "distinct_cited_keys": len({k for g in groups for k in g["keys"]}),
        "todo_note_groups": sum(1 for c in citations if c["omitted_in_docx"]),
        "keys_only_in_todo_notes": sorted(
            {k for c in citations if c["omitted_in_docx"] for k in c["keys"]}
            - {k for c in citations if not c["omitted_in_docx"] for k in c["keys"]}
        ),
        "distinct_keys_outside_todo": len({k for c in citations if not c["omitted_in_docx"] for k in c["keys"]}),
        "aligned_groups": sum(1 for c in citations if c["docx"] is not None),
        "unaligned_keys": sorted({k for c in citations if c["docx"] is None and not c["omitted_in_docx"] for k in c["keys"]}),
    },
}
Path(sys.argv[2]).write_text(json.dumps(oracle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(oracle["counts"], ensure_ascii=False))
