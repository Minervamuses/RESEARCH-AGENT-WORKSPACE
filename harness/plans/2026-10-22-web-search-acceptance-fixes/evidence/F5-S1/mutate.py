"""Apply one F5-S1 mutation to a scratch copy of the vendor src: python -I mutate.py <copy> <id>"""
import sys
from pathlib import Path

EDITS = {
    # Zero candidates always read as "all failed".
    "N02b": ("src/utils.ts", "    lines.push(!ran.length ?", "    lines.push(true ? 'All attempted engines failed; no candidates are available.' : !ran.length ?"),
    # Engine lines drop the error reason.
    "N02c": ("src/utils.ts", "      engine.error && `error=${engine.error}`,\n", ""),
    # strategy_stopped engines are left out of the text.
    "N02d": ("src/utils.ts", "  for (const engine of engines) {\n", "  for (const engine of engines.filter(e => e.status !== 'strategy_stopped')) {\n"),
    # Merged candidates show only the first source engine.
    "N02g": ("src/utils.ts", "`Source engines: ${(result.sourceEngines ?? []).join(', ')}`", "`Source engines: ${(result.sourceEngines ?? []).slice(0, 1).join(', ')}`"),
    # Admission ignores the limit.
    "N03b": ("src/search-engine.ts", "      while (results.length < numResults && queue.length) {", "      while (queue.length) {"),
}
name, old, new = EDITS[sys.argv[2]]
target = Path(sys.argv[1]) / name
text = target.read_text()
assert text.count(old) == 1, sys.argv[2]
target.write_text(text.replace(old, new, 1))
