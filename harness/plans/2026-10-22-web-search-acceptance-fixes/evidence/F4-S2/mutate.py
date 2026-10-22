"""Apply one F4-S2 variant to a scratch copy of the vendor src: python -I mutate.py <copy> <N28|N29>"""
import sys
from pathlib import Path

target = Path(sys.argv[1]) / "src/browser-pool.ts"
text = target.read_text()
old, new = {
    "N28": ("      try { process.kill(-pid, 'SIGKILL'); } catch { /* Already exited. */ }\n", ""),
    # boundedClose no longer races the cleanup timer.
    "N29": ("    await Promise.race([\n      close(),\n      new Promise<never>((_resolve, reject) => {\n"
            "        timer = setTimeout(() => reject(new Error('Resource cleanup timeout')), OPERATION_TIMEOUTS.cleanup);\n"
            "      }),\n    ]);\n", "    await close();\n"),
}[sys.argv[2]]
assert text.count(old) == 1
target.write_text(text.replace(old, new, 1))
