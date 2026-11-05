"""Render the thesis copy with bime-appendix17.csl and compare with the oracle.

Usage (from app/): python compare_appendix17.py <thesis-copy-dir> <oracle.json> <out-dir>
Writes comparison.json and compare.md (citation and bibliography strings only).
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from skills.citation.csl_render import render

thesis, oracle_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
rendered = render((thesis / "proposal.md").read_text(encoding="utf-8"), thesis / "references.json", "bime-appendix17")


def norm(text):
    text = unicodedata.normalize("NFC", text or "").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


todo_only = set(oracle["counts"]["keys_only_in_todo_notes"])
cit_rows = []
for group, ours in zip(oracle["citations"], rendered.citations):
    assert group["keys"] == ours["keys"], (group["keys"], ours["keys"])
    if group["omitted_in_docx"]:
        continue
    cit_rows.append({"keys": group["keys"], "oracle": group["docx"], "csl": norm(ours["text"]),
                     "match": norm(group["docx"]) == norm(ours["text"])})
ours_bib = [e for e in rendered.bibliography if e["key"] not in todo_only]
bib_rows = []
for index, docx in enumerate(oracle["bibliography"]):
    entry = ours_bib[index] if index < len(ours_bib) else {"key": None, "text": ""}
    bib_rows.append({"position": index, "key": entry["key"], "oracle": docx, "csl": norm(entry["text"]),
                     "match": norm(docx) == norm(entry["text"])})
summary = {
    "citations": {"total": len(cit_rows), "match": sum(r["match"] for r in cit_rows)},
    "bibliography": {"total": len(bib_rows), "match": sum(r["match"] for r in bib_rows),
                     "csl_entries": len(ours_bib)},
}
(out / "comparison.json").write_text(json.dumps({"summary": summary, "citations": cit_rows, "bibliography": bib_rows},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(summary))
for row in cit_rows + bib_rows:
    if not row["match"]:
        print("--", row.get("key") or row["keys"])
        print("   oracle:", row["oracle"])
        print("   csl:   ", row["csl"])
