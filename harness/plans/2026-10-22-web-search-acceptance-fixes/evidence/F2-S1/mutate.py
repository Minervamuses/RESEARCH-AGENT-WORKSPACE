"""Apply one F2-S1 discrimination variant to a scratch copy's agent/mcp.py.

usage: python -I mutate.py <copy>/agent/mcp.py <variant> [<old-mcp.py>]
variants: old (HEAD logic plus the test helper _proc_stat), P07, P27
"""
import sys
from pathlib import Path

target, variant = Path(sys.argv[1]), sys.argv[2]
text = target.read_text()
if variant == "old":
    old = Path(sys.argv[3]).read_text()
    helper = text[text.index("def _proc_stat("):text.index("async def _bounded_web_search(")]
    text = old.replace("async def _bounded_web_search(", helper + "async def _bounded_web_search(", 1)
elif variant == "P07":
    edit = ("            expanded = family | {pid for pid, record in records.items() if record[1] in family}\n",
            "            expanded = family\n")
    assert edit[0] in text
    text = text.replace(*edit, 1)
elif variant == "P27":
    edit = ("        while not stop.is_set():\n            observe_once()\n",
            "        while not stop.is_set():\n")
    assert edit[0] in text
    text = text.replace(*edit, 1)
else:
    raise SystemExit(f"unknown variant {variant}")
target.write_text(text)
