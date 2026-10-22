"""Apply one F2-S2 variant to a scratch copy of app/: python -I mutate.py <copy> <variant> [<HEAD mcp.py>]"""
import sys
from pathlib import Path

copy, variant = Path(sys.argv[1]), sys.argv[2]
EDITS = {
    "P13": ("agent/startup.py", "                diagnostics=runtime_diagnostics,\n", ""),
    "P13c": ("agent/startup.py", '            runtime_diagnostics.append(\n                "MCP loader unavailable: " + type(exc).__name__\n            )\n', "            pass\n"),
    "P18": ("agent/mcp.py", 'int(spec.env.get("DEFAULT_TIMEOUT", "300000"))', "300000"),
    "P18b": ("agent/mcp.py", "if not 1 <= timeout_ms <= 300000:", "if not 1 <= timeout_ms <= 600000:"),
    "P26": ("agent/mcp.py", "            await asyncio.wait({task}, timeout=max(0, deadline - loop.time()))\n", "            await asyncio.wait({task})\n"),
}
if variant == "old":
    (copy / "agent/mcp.py").write_text(Path(sys.argv[3]).read_text())
else:
    name, old, new = EDITS[variant]
    target = copy / name
    text = target.read_text()
    assert text.count(old) == 1, (variant, text.count(old))
    target.write_text(text.replace(old, new, 1))
