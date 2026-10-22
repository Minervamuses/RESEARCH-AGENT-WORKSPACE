"""F7-S3 public observation (run outside the host sandbox): python observe.py <short-scratch-dir> [group ...]

Budget: at most six groups and eight minutes of group time in total; Google searches at least 10 s apart;
blocked engines are never retried. groups.jsonl gets a start record before and an end record after every
group, and a resumed run skips groups that already have a start record. Groups 1-3 use the Python entry
with the product's custom command plus an observe-only preload (observe.mjs) that records structure counts
of the very page the engine parsed; group 4 uses the dist adapter and is not the full Python chain.
"""
import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
DIST = REPO / "app/vendor/web-search-mcp/dist/index.js"
SCRATCH = Path(sys.argv[1]).resolve()
ONLY = set(sys.argv[2:])
GROUPS = HERE / "groups.jsonl"
BUDGET_S = 480
for name in ("cache", "log"):
    (SCRATCH / name).mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(SCRATCH / "cache")
os.environ["AGENT_LOG_DIR"] = str(SCRATCH / "log")
for name in ("AGENT_MCP_WEB_SEARCH_COMMAND", "AGENT_MCP_WEB_SEARCH_ARGS", "AGENT_ENABLE_MCP_GITHUB", "MAX_CONTENT_LENGTH",
             "DEFAULT_TIMEOUT", "BROWSER_HEADLESS", "MAX_CONCURRENT_PAGES", "MAX_CONCURRENT_HTTP"):
    os.environ.pop(name, None)
sys.path.insert(0, str(REPO / "app"))
from agent import mcp  # noqa: E402

NODE = shutil.which("node")


def records():
    return [json.loads(line) for line in GROUPS.read_text().splitlines() if line.strip()] if GROUPS.exists() else []


def append(record):
    with GROUPS.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def spent():
    return sum(r.get("elapsed_s", 0) for r in records() if r.get("phase") == "end")


def last_google():
    times = [r["google_at"] for r in records() if r.get("google_at")]
    return max(times) if times else 0


async def python_entry(group, tool, args, timeout_ms):
    log = SCRATCH / f"structure-{group}.jsonl"
    log.write_text("")
    url = (HERE / "observe.mjs").as_uri() + "?log=" + quote(str(log), safe="")
    env = {"AGENT_MCP_WEB_SEARCH_COMMAND": NODE, "AGENT_MCP_WEB_SEARCH_ARGS": shlex.join(["--import", url, str(DIST)]),
           "DEFAULT_TIMEOUT": str(timeout_ms)}
    os.environ.update(env)
    try:
        diagnostics = []
        specs = mcp.resolve_mcp_specs(diagnostics=diagnostics)
        tools, _families = await mcp.load_mcp_tools_with_families(specs=specs, diagnostics=diagnostics)
        tools = {t.name: t for t in tools}
        begin = time.monotonic()
        try:
            response = await tools[tool].ainvoke(args)
            text = response if isinstance(response, str) else "\n".join(part.get("text", "") for part in response)
            error = None
        except Exception as exc:
            text, error = "", f"{type(exc).__name__}: {exc}"
        return {"tool": tool, "args": args, "call_ms": round((time.monotonic() - begin) * 1000), "diagnostics": diagnostics,
                "error": error, "output": text, "structure": [json.loads(l) for l in log.read_text().splitlines() if l.strip()]}
    finally:
        for key in env:
            os.environ.pop(key, None)


def facts(output):
    lines = output.splitlines()
    engines = [l for l in lines if l.startswith("- Google:") or l.startswith("- Bing:")]
    candidates = []
    for block in output.split("\n\n**")[1:]:
        if not block.split("**", 1)[0][:1].isdigit():
            continue  # "**Page content:**" sections are not candidates
        rows = block.splitlines()
        pick = lambda prefix: next((r[len(prefix):] for r in rows if r.startswith(prefix)), None)
        candidates.append({"url": pick("URL: "), "link": pick("Link: "), "read_status": pick("Read status: "), "sources": pick("Source engines: ")})
    links = [c["link"] for c in candidates if c["link"]]
    resolved = [l for l in links if "resolved by navigation" in l and "not resolved" not in l]
    return {"engines": engines, "candidates": candidates, "resolved": len(resolved), "unresolved": len(links) - len(resolved),
            "resolution_ms": [int(l.rsplit(" in ", 1)[1].split()[0]) for l in resolved],
            "stats": next((l for l in lines if l.startswith("Read statistics:")), None)}


PLAN = [
    (1, "Google", "full-web-search", {"query": "python asyncio TaskGroup exception handling", "limit": 5, "includeContent": True, "maxContentLength": 1500}, 90000,
     "A general technical question with stable documentation; reads five pages."),
    (2, "Google", "get-web-search-summaries", {"query": "台股 今日 收盤 行情", "limit": 5}, 60000,
     "A Chinese current-events query (today's Taiwan stock market close) exercising the zh-TW market."),
    (3, None, "get-single-web-page-content", None, 60000, "One resolved target URL from group 1 (else group 2)."),
    (4, "Google", "dist-adapter", {"query": "how does TCP congestion control work"}, 120000,
     "Each engine on its own through the dist adapter; not the full Python chain."),
    # Added after groups 1-4: Google filled every limit, so Bing filling was never observed.
    (5, "Google", "get-web-search-summaries", {"query": "Playwright channel chromium new headless mode", "limit": 10}, 60000,
     "Observe Bing filling when Google returns fewer candidates than the limit (limit 10)."),
    # Added after group 5: Bing returned zero organic items twice; record what its result list holds.
    (6, None, "bing-probe", {"query": "how does photosynthesis work"}, 60000,
     "Bing alone (dist adapter) with a query OD1 saw answered under setlang=en&cc=US; records the #b_results children."),
]


async def main():
    done = {r["group"] for r in records() if r.get("phase") == "start"}
    previous = {r["group"]: r for r in records() if r.get("phase") == "end"}
    for group, google, tool, args, timeout_ms, reason in PLAN:
        if group in done or (ONLY and str(group) not in ONLY):
            continue
        cap_s = timeout_ms / 1000 + 30
        if spent() + cap_s > BUDGET_S:
            append({"group": group, "phase": "skipped", "reason": f"remaining budget {BUDGET_S - spent():.0f} s below the group cap {cap_s:.0f} s"})
            continue
        if tool == "get-single-web-page-content":
            pool = [c for g in (1, 2) for c in previous.get(g, {}).get("facts", {}).get("candidates", [])]
            resolved = [c["url"] for c in pool if c["link"] and "resolved by navigation" in c["link"] and "not resolved" not in c["link"]]
            url = (resolved or [c["url"] for c in pool if c["url"]] or [None])[0]
            if not url:
                append({"group": group, "phase": "skipped", "reason": "no URL from groups 1 and 2; recorded as unverified"})
                continue
            args = {"url": url}
        if google:
            wait = 10 - (time.time() - last_google())
            if wait > 0:
                time.sleep(wait)
        start = time.time()
        append({"group": group, "phase": "start", "tool": tool, "args": args, "reason": reason, "started_at": start,
                **({"google_at": start} if google else {})})
        if tool == "bing-probe":
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
            env.update(TMPDIR=str(SCRATCH), PLAYWRIGHT_BROWSERS_PATH=str(Path.home() / ".cache/ms-playwright"))
            done_run = subprocess.run([NODE, str(HERE / "bing_probe.mjs"), str(DIST.parent), args["query"]], env=env,
                                      capture_output=True, text=True, timeout=timeout_ms / 1000)
            summary = json.loads(done_run.stdout.strip().splitlines()[-1]) if done_run.returncode == 0 else {"exit": done_run.returncode, "stderr": done_run.stderr[-2000:]}
        elif tool == "dist-adapter":
            env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
            env.update(TMPDIR=str(SCRATCH), PLAYWRIGHT_BROWSERS_PATH=str(Path.home() / ".cache/ms-playwright"))
            done_run = subprocess.run([NODE, str(HERE / "group4.mjs"), str(DIST.parent), args["query"]], env=env,
                                      capture_output=True, text=True, timeout=timeout_ms / 1000)
            summary = json.loads(done_run.stdout.strip().splitlines()[-1]) if done_run.returncode == 0 else {"exit": done_run.returncode, "stderr": done_run.stderr[-2000:]}
        else:
            result = await python_entry(group, tool, args, timeout_ms)
            summary = {"facts": facts(result["output"]), "error": result["error"], "call_ms": result["call_ms"], "structure": result["structure"],
                       "diagnostics": result["diagnostics"], "output": result["output"]}
        end = time.time()
        append({"group": group, "phase": "end", "elapsed_s": round(end - start, 1), **summary})
        previous[group] = {"facts": summary.get("facts", {})}
        print(f"group {group}: {round(end - start, 1)} s", flush=True)
    print(json.dumps({"spent_s": spent(), "groups": sorted({r['group'] for r in records() if r.get('phase') == 'end'})}), flush=True)


asyncio.run(main())
