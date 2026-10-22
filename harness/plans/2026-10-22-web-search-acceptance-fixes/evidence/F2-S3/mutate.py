"""Apply one F2-S3 variant to a scratch copy of app/: python -I mutate.py <copy> <variant>
trap: tool calls use the startup cap (the pitfall in phase-2); uncapped: discovery keeps DEFAULT_TIMEOUT."""
import sys
from pathlib import Path

copy, variant = Path(sys.argv[1]), sys.argv[2]
target = copy / "agent/mcp.py"
text = target.read_text()
old, new = {
    "trap": ("        return await _bounded_web_search(connection, execute, timeout_ms)\n",
             "        return await _bounded_web_search(connection, execute, startup_ms)\n"),
    "uncapped": ("    startup_ms = min(WEB_SEARCH_STARTUP_TIMEOUT_MS, timeout_ms)\n", "    startup_ms = timeout_ms\n"),
}[variant]
assert text.count(old) == 1
target.write_text(text.replace(old, new, 1))
