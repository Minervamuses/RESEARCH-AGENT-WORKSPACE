"""F6-S3 mutation re-check (context/mutation-survivors.md).

usage: python -I run_mutations.py <repo-root> <scratch-root> [ids...]
       python -I run_mutations.py <repo-root> <scratch-root> --reasons <ids...>
         re-runs recorded kills only to name the failing assertion (reasons.jsonl); verdicts stay in results.jsonl

Copies outside the repository, never touching the repo's dist or production files:
  node: app/vendor/web-search-mcp/{src,tests,package.json,tsconfig.json}, node_modules symlinked, own dist via tsc
  python: app/{agent,skills,rag,tests,pyproject.toml,poetry.toml}, app/vendor symlinked (no app/desktop, no app/store)
Each copy runs an unmutated control first. A mutation is killed when at least one test exits non-zero
(a test timeout counts). Results are appended to results.jsonl next to this script; recorded ids are skipped.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.jsonl"
REPO, SCRATCH = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
REASONS = sys.argv[3:4] == ["--reasons"]
ONLY = set(sys.argv[4:] if REASONS else sys.argv[3:])
VENDOR = REPO / "app/vendor/web-search-mcp"
NODE_BIN = Path(sys.executable).parent / "node"
NODE_TESTS = ["test-search-result-retention.mjs", "test-content-contract.mjs", "test-browser-lifecycle.mjs", "test-server-entry.mjs"]
PY_TESTS = ["tests/test_mcp.py", "tests/test_mcp_stderr_log.py", "tests/test_extension_mcp.py"]

# id: (category, [(file, old, new), ...]); each old text must occur exactly once.
NODE = {
    "N02b": ("must", [("src/utils.ts", "    lines.push(!ran.length ?", "    lines.push(true ? 'All attempted engines failed; no candidates are available.' : !ran.length ?")]),
    "N02c": ("must", [("src/utils.ts", "      engine.error && `error=${engine.error}`,\n", "")]),
    "N02d": ("must", [("src/utils.ts", "  for (const engine of engines) {\n", "  for (const engine of engines.filter(e => e.status !== 'strategy_stopped')) {\n")]),
    "N02g": ("must", [("src/utils.ts", "`Source engines: ${(result.sourceEngines ?? []).join(', ')}`", "`Source engines: ${(result.sourceEngines ?? []).slice(0, 1).join(', ')}`")]),
    "N03b": ("must", [("src/search-engine.ts", "      while (results.length < numResults && queue.length) {", "      while (queue.length) {")]),
    "N05d": ("must", [("src/utils.ts", "parseInteger(process.env.MAX_CONTENT_LENGTH, 'MAX_CONTENT_LENGTH', 1, 10000)", "parseInteger(process.env.MAX_CONTENT_LENGTH, 'MAX_CONTENT_LENGTH', 0, 10000)")]),
    "N06d": ("must", [("src/utils.ts", "truncated: true, originalLength: points.length, returnedLength: boundary", "truncated: true, originalLength: text.length, returnedLength: boundary")]),
    "N07c": ("must", [("src/enhanced-content-extractor.ts", "    $('script, style, noscript, template').remove();\n",
                       "    $('script, style, noscript, template').remove();\n    $(['nav', 'footer', 'comment', 'sidebar', 'menu', 'banner', 'cookie'].flatMap(n => [`[class*=\"${n}\"]`, `[id*=\"${n}\"]`]).join(', ')).remove();\n")]),
    "N07e": ("must", [("src/enhanced-content-extractor.ts", "    let baseUrl = finalUrl;\n", "    let baseUrl = 'https://wrong.example/';\n"),
                      ("src/enhanced-content-extractor.ts", "const resolved = new URL(declaredBase, finalUrl);", "const resolved = new URL(declaredBase, baseUrl);")]),
    "N07f": ("must", [("src/enhanced-content-extractor.ts", "    const declaredBase = $('base[href]').first().attr('href');", "    const declaredBase = undefined as string | undefined;")]),
    "N08h": ("must", [("src/browser-pool.ts", "          headless: process.env.BROWSER_HEADLESS !== 'false',", "          headless: true,")]),
    "N08i": ("must", [("src/browser-pool.ts", "    if (headless !== undefined && !['true', 'false'].includes(headless)) {", "    if (false) {")]),
    "N09g": ("must", [("src/browser-pool.ts", "      return await budget.wait(this.pages(async () => {", "      return await (this.pages(async () => {")]),
    "N11b": ("must", [("src/index.ts", "    process.stdin.once('end', stop);\n    process.stdin.once('close', stop);\n", "")]),
    "N11c": ("must", [("src/index.ts", "    process.once('SIGTERM', stop);\n", "")]),
    "N11d": ("must", [("src/index.ts", "      for (const budget of this.activeBudgets) budget.abort();\n", "")]),
    "N11e": ("must", [("src/index.ts", "      try { await sharedBrowserPool.closeAll(); }", "      try { /* pool left open */ }")]),
    "N12": ("must", [("src/index.ts", "            query, searchResponse.results, searchResponse.engines,\n          );\n",
                      "            query, searchResponse.results, searchResponse.engines,\n          );\n          await sharedBrowserPool.closeAll();\n")]),
    "N13": ("must", [("src/index.ts", "      const enhancedResults = includeContent\n", "      const enhancedResults = true\n")]),
    "N13b": ("must", [("src/index.ts", "          const responseText = formatSearchResponse(\n            query, searchResponse.results,",
                       "          searchResponse.results = await this.contentExtractor.extractContentForResults(searchResponse.results, limit, undefined, budget);\n          const responseText = formatSearchResponse(\n            query, searchResponse.results,")]),
    "N14": ("must", [("src/index.ts", "extra._meta?.web_search_work_ms", "extra._meta?.web_search_work_milliseconds")]),
    "N14b": ("must", [("src/index.ts", "      ? Math.max(0, Math.min(work, remaining)) : work;", "      ? work : work;")]),
    "N14c": ("must", [("src/index.ts", "new CallBudget(duration, extra.signal)", "new CallBudget(duration)")]),
    "N14d": ("must", [("src/index.ts", "const maxContentLength = resolveContentLimit(obj.maxContentLength);", "const maxContentLength = resolveContentLimit(undefined);")]),
    "N14f": ("must", [("src/index.ts", "result.query, result.results, result.engines ?? [], validatedArgs.includeContent,", "result.query, result.results, result.engines ?? [], false,")]),
    "N14g": ("must", [("src/index.ts", "            query, searchResponse.results, searchResponse.engines,\n", "            query, searchResponse.results, [],\n")]),
    "N14h": ("must", [("src/index.ts", "            query,\n            numResults: limit,\n", "            query,\n")]),
    "N14i": ("must", [("src/index.ts", "        engines: searchResponse.engines,\n", "        engines: [],\n")]),
    "N14j": ("must_conditional", [("src/index.ts",
              "limit: z.union([z.number(), z.string()]).transform(val => parseInteger(val, 'limit', 1, 10)).default(5).describe('Number of search results to return (1-10)'),",
              "limit: z.union([z.number(), z.string()]).default(5).describe('Number of search results to return (1-10)'),")]),
    "N16c": ("must", [("src/enhanced-content-extractor.ts", "          waitUntil: 'domcontentloaded', timeout: options.budget.timeout(OPERATION_TIMEOUTS.pageRequest),\n", "          waitUntil: 'domcontentloaded',\n")]),
    "N20b": ("must", [("src/enhanced-content-extractor.ts", "results.map(async (result, index) => index >= targetCount ? { ...result } : {", "results.map(async (result, index) => index >= Infinity ? { ...result } : {")]),
    # The call signal is dropped from the HTTP read; only the local operation timer remains.
    "N26": ("must", [("src/enhanced-content-extractor.ts", "signal: AbortSignal.any([options.budget.signal, operation.signal])", "signal: operation.signal")]),
    "N28": ("must", [("src/browser-pool.ts", "      try { process.kill(-pid, 'SIGKILL'); } catch { /* Already exited. */ }\n", "")]),
    "N29": ("must", [("src/browser-pool.ts",
              "    await Promise.race([\n      close(),\n      new Promise<never>((_resolve, reject) => {\n        timer = setTimeout(() => reject(new Error('Resource cleanup timeout')), OPERATION_TIMEOUTS.cleanup);\n      }),\n    ]);\n",
              "    await close();\n")]),
    "N42": ("must", [("src/browser-pool.ts", "  return Math.min(15000, Math.max(1500, total * 0.05), total / 2);", "  return 0;")]),
    "N43": ("must", [("src/browser-pool.ts", "Number(raw) > 300000)", "Number(raw) > 3000000)")]),
    "N09b": ("optional", [("src/browser-pool.ts", "    if (this.parentAbort) this.parent?.removeEventListener('abort', this.parentAbort);\n", "")]),
}
NOT_APPLICABLE = {
    "N04c": "Brave URL cleaning was deleted with Brave in F3-S2 (FU01).",
    "N15": "Brave's transient retry loop was deleted with Brave in F3-S2 (FU01).",
    "N16b": "Brave's goto was deleted with Brave in F3-S2 (FU01).",
    "N16e": "Bing's homepage form flow and its waitForNavigation were deleted in F3-S2; Bing now navigates the search URL directly.",
    "N16f": "Brave's result selector wait was deleted with Brave in F3-S2 (FU01).",
    "N17": "The DuckDuckGo axios request was deleted with DuckDuckGo in F3-S2 (FU01).",
}
PYTHON = {
    "P07": ("must", [("agent/mcp.py", "            expanded = family | {pid for pid, record in records.items() if record[1] in family}\n", "            expanded = family\n")]),
    "P27": ("must", [("agent/mcp.py", "        while not stop.is_set():\n            observe_once()\n", "        while not stop.is_set():\n")]),
    "P13": ("must", [("agent/startup.py", "                diagnostics=runtime_diagnostics,\n", "")]),
    "P13c": ("must", [("agent/startup.py", '            runtime_diagnostics.append(\n                "MCP loader unavailable: " + type(exc).__name__\n            )\n', "            pass\n")]),
    "P18": ("must", [("agent/mcp.py", 'int(spec.env.get("DEFAULT_TIMEOUT", "300000"))', "300000")]),
    "P18b": ("must", [("agent/mcp.py", "if not 1 <= timeout_ms <= 300000:", "if not 1 <= timeout_ms <= 600000:")]),
    "P26": ("must", [("agent/mcp.py", "            await asyncio.wait({task}, timeout=max(0, deadline - loop.time()))\n", "            await asyncio.wait({task})\n")]),
    "P07b": ("optional", [("agent/mcp.py", "                    os.killpg(pid, signal.SIGKILL)\n", "                    os.kill(pid, signal.SIGKILL)\n")]),
    "P07d": ("optional", [("agent/mcp.py", '                if record is None or record[3] != started or record[0] == "Z":\n', '                if record is None or record[0] == "Z":\n')]),
}


def recorded() -> set[str]:
    if not RESULTS.exists():
        return set()
    return {json.loads(line)["id"] for line in RESULTS.read_text().splitlines() if line.strip()}


def append(entry: dict) -> None:
    with RESULTS.open("a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def apply(root: Path, edits) -> None:
    for name, old, new in edits:
        target = root / name
        text = target.read_text()
        if text.count(old) != 1:
            raise RuntimeError(f"{name}: expected exactly one match, found {text.count(old)}")
        target.write_text(text.replace(old, new, 1))


def run(command, cwd, env, timeout):
    begin = time.monotonic()
    try:
        done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return done.returncode, done.stdout + done.stderr, round(time.monotonic() - begin, 1)
    except subprocess.TimeoutExpired as expired:
        output = (expired.stdout or b"") + (expired.stderr or b"")
        return "timeout", output.decode(errors="replace") if isinstance(output, bytes) else output, round(time.monotonic() - begin, 1)


def first_failure_line(output: str) -> str:
    for line in output.splitlines():
        if line.startswith(("not ok", "AssertionError", "FAILED", "E  ")) or "Error:" in line:
            return line.strip()[:200]
    return output.strip().splitlines()[-1][:200] if output.strip() else ""


def failing_assertion(output: str) -> str:
    """The first assertion message (skipping known injected-failure logs), a pytest --tb=line entry, or not ok."""
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("AssertionError"):
            detail = [l.strip() for l in lines[index + 1:index + 6] if l.strip() and not l.startswith("    at ") and not l.strip().startswith("generatedMessage")]
            return " ".join([line.strip(), *detail[:3]])[:300]
        if "/tests/test_" in line and ": " in line and line.split(":")[1].strip().isdigit():
            return line.split("/tests/", 1)[1].strip()[:300]
    for line in lines:
        if line.startswith("not ok"):
            return line.strip()[:300]
    return first_failure_line(output)


def node_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH")}
    return env


def node_suite(root: Path) -> tuple[str, str, list]:
    build = subprocess.run([str(NODE_BIN), "node_modules/typescript/bin/tsc"], cwd=root, capture_output=True, text=True)
    if build.returncode:
        return "build_failed", build.stdout[-300:], []
    runs = []
    for test in NODE_TESTS:
        code, output, seconds = run([str(NODE_BIN), f"tests/{test}"], root, node_env(), 150)
        runs.append({"test": test, "exit": code, "seconds": seconds})
        if code != 0:
            return test, first_failure_line(output), runs
    return "", "", runs


def py_env(root: Path) -> dict:
    env = node_env()
    for name in ("cache", "log", "tmp"):
        (root / f".{name}").mkdir(exist_ok=True)
    env.update(XDG_CACHE_HOME=str(root / ".cache"), AGENT_LOG_DIR=str(root / ".log"), TMPDIR=str(root / ".tmp"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root))
    return env


def py_suite(root: Path) -> tuple[str, str, list]:
    code, output, seconds = run([sys.executable, "-m", "pytest", *PY_TESTS, "-q", "-p", "no:cacheprovider", "-x"], root, py_env(root), 400)
    runs = [{"test": " ".join(PY_TESTS), "exit": code, "seconds": seconds}]
    if code != 0:
        failed = [line for line in output.splitlines() if line.startswith("FAILED")]
        return (failed[0].split(" ")[1] if failed else "pytest"), first_failure_line(output), runs
    return "", "", runs


def fresh_node() -> Path:
    root = SCRATCH / "node"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for name in ("src", "tests"):
        shutil.copytree(VENDOR / name, root / name)
    for name in ("package.json", "tsconfig.json"):
        shutil.copy2(VENDOR / name, root / name)
    (root / "node_modules").symlink_to(VENDOR / "node_modules")
    return root


def fresh_python() -> Path:
    root = SCRATCH / "python"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for name in ("agent", "skills", "rag", "tests"):
        shutil.copytree(REPO / "app" / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "poetry.toml"):
        shutil.copy2(REPO / "app" / name, root / name)
    (root / "vendor").symlink_to(REPO / "app/vendor")
    return root


def reasons() -> None:
    target = HERE / "reasons.jsonl"
    for ident in ONLY:
        kind = "node" if ident in NODE else "python"
        category, edits = (NODE if kind == "node" else PYTHON)[ident]
        root = fresh_node() if kind == "node" else fresh_python()
        apply(root, edits)
        if kind == "node":
            subprocess.run([str(NODE_BIN), "node_modules/typescript/bin/tsc"], cwd=root, capture_output=True, check=True)
            for test in NODE_TESTS:
                code, output, seconds = run([str(NODE_BIN), f"tests/{test}"], root, node_env(), 150)
                if code != 0:
                    break
        else:
            test = "tests/test_mcp.py"
            code, output, seconds = run([sys.executable, "-m", "pytest", *PY_TESTS, "-q", "-p", "no:cacheprovider", "-x", "--tb=line"], root, py_env(root), 400)
        reason = f"timed out after {seconds} s" if code == "timeout" else failing_assertion(output)
        entry = {"id": ident, "test": test, "exit": code, "reason": reason}
        with target.open("a") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(json.dumps(entry, ensure_ascii=False), flush=True)


def main() -> None:
    if REASONS:
        return reasons()
    done = recorded()
    wanted = lambda ident: (not ONLY or ident in ONLY) and ident not in done
    for ident, reason in NOT_APPLICABLE.items():
        if wanted(ident):
            append({"id": ident, "category": "not_applicable", "result": "not_applicable", "reason": reason})
    for kind, table, fresh, suite in (("node", NODE, fresh_node, node_suite), ("python", PYTHON, fresh_python, py_suite)):
        pending = [ident for ident in table if wanted(ident)]
        if not pending:
            continue
        failed, line, runs = suite(fresh())
        control = {"id": f"control-{kind}", "category": "control", "result": "green" if not failed else "red", "runs": runs}
        print(json.dumps(control), flush=True)
        if failed:
            raise SystemExit(f"{kind} control is not green ({failed}: {line}); fix the copy before counting mutations")
        for ident in pending:
            category, edits = table[ident]
            root = fresh()
            apply(root, edits)
            failed, line, runs = suite(root)
            append({"id": ident, "category": category, "result": "killed" if failed else "survived",
                    "failed_test": failed or None, "first_failure": line or None, "runs": runs})


main()
