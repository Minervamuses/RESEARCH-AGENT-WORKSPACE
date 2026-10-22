"""F7-S2: real Python -> wrapper -> dist acceptance on a local server (run outside the host sandbox).

usage: python drive.py <short-scratch-dir> [case ...]

Loads web_search exactly like the Agent (agent.mcp.resolve_mcp_specs + load_mcp_tools_with_families).
Cases that need fixed candidates or fake engines use the product's AGENT_MCP_WEB_SEARCH_COMMAND/ARGS with
`node --import preload.mjs?<query> <dist>/index.js`; this still runs the product loader, wrapper and
environment allowlist (noted per case). Each case samples its own descendant processes and checks for
survivors in the same script; only recorded survivors are killed.
"""
import asyncio
import gc
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
DIST = REPO / "app/vendor/web-search-mcp/dist/index.js"
SCRATCH = Path(sys.argv[1]).resolve()
ONLY = set(sys.argv[2:])
for name in ("cache", "log"):
    (SCRATCH / name).mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(SCRATCH / "cache")
os.environ["AGENT_LOG_DIR"] = str(SCRATCH / "log")
for name in ("AGENT_MCP_WEB_SEARCH_COMMAND", "AGENT_MCP_WEB_SEARCH_ARGS", "AGENT_ENABLE_MCP_GITHUB", "MAX_CONTENT_LENGTH",
             "DEFAULT_TIMEOUT", "BROWSER_HEADLESS", "MAX_CONCURRENT_PAGES", "MAX_CONCURRENT_HTTP", "AGENT_ENABLE_MCP_WEB_SEARCH"):
    os.environ.pop(name, None)
sys.path.insert(0, str(REPO / "app"))
from agent import mcp  # noqa: E402

NODE = shutil.which("node")
LOG: list[dict] = []
captured: list[str] = []


class Capture(logging.Handler):
    def emit(self, record):
        captured.append(record.getMessage() + ("\n" + logging.Formatter().formatException(record.exc_info) if record.exc_info else ""))


logging.getLogger().addHandler(Capture(level=logging.DEBUG))
logging.getLogger().setLevel(logging.DEBUG)

# ---------------------------------------------------------------- local server (127.0.0.1 only)
PDF_SMALL = b"%PDF-1.7\n%fake\n"


def nested(depth: int) -> str:
    inner = "LEAF"
    for level in range(1, depth + 1):
        inner = f"<table><tr><td>L{level}x</td><td>{inner}</td></tr></table>"
    return f"<html><body>{inner}</body></html>"


LATE = {
    "timer300": "<script>setTimeout(() => document.body.insertAdjacentHTML('beforeend', '<p>TARGET timer 300</p>'), 300)</script>",
    "navfetch": "<script>document.write('<nav>Site menu Home About</nav>');"
                "fetch('/data?ms=300&text=TARGET%20main%20after%20nav').then(r => r.text()).then(t => document.body.insertAdjacentHTML('beforeend', '<p>' + t + '</p>'))</script>",
    "late5000": "<script>setTimeout(() => document.body.insertAdjacentHTML('beforeend', '<p>TARGET too late</p>'), 5000)</script>",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def send(self, status, ctype, body: bytes, **headers):
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in headers.items():
            self.send_header(key.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(body)

    def hang(self):
        self.close_connection = True
        end = time.time() + 120
        while time.time() < end and not STOP.is_set():
            time.sleep(0.1)

    def do_GET(self):
        url = urlsplit(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        ua = self.headers.get("User-Agent", "")
        reader = "Chrome/121." in ua  # the product's HTTP reader; the browser sends its own major version
        LOG.append({"path": url.path, "query": query, "host": self.headers.get("Host"), "http_reader": reader,
                    "referer": self.headers.get("Referer"), "at": time.time()})
        port = self.server.server_address[1]
        target = lambda name: f"http://127.0.0.1:{port}/target/{name}"
        html = lambda text, status=200, **h: self.send(status, "text/html; charset=utf-8", text.encode(), **h)
        path = url.path
        if path.startswith("/nested/"):
            return html(nested(int(path.split("/")[-1])))
        if path == "/articles":
            return html("<p>Intro</p><article><h2>Story 1</h2></article><article><h2>Story 2</h2></article>"
                        "<aside><article>Related</article></aside><main>Main</main><p>Tail</p>")
        if path == "/big5":
            return self.send(200, "text/html; charset=big5", b"<p>\xa4\xa4\xa4\xe5</p>")
        if path == "/sjis":
            return self.send(200, "text/html", b'<meta charset="shift_jis"><p>\x93\xfa\x96\x7b</p>')
        if path.startswith("/late/"):
            return html(f"<html><head><title>late</title></head><body>{LATE[path.split('/')[-1]]}</body></html>")
        if path == "/data":
            time.sleep(int(query.get("ms", "0")) / 1000)
            return self.send(200, "text/plain", query.get("text", "").encode())
        if path == "/ua":
            return html("<html><body></body></html>" if reader else f"<html><body><p>UA: {ua}</p></body></html>")
        if path == "/drip":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            end = time.time() + 60
            try:
                while time.time() < end and not STOP.is_set():
                    self.wfile.write(b"a")
                    self.wfile.flush()
                    time.sleep(0.3)
            except OSError:
                pass
            return None
        if path == "/big.pdf":
            return self.send(200, "application/pdf", PDF_SMALL + b"\0" * (11 * 1024 * 1024))
        if path == "/big.html":
            return self.send(200, "text/html", b"a" * (11 * 1024 * 1024))
        if path == "/deny-pdf":
            return html("<p>denied</p>", 403) if reader else self.send(200, "application/pdf", PDF_SMALL)
        if path.startswith("/slow/"):
            time.sleep(2)
            return html(f"<html><body><p>Slow page {path.split('/')[-1]}</p></body></html>")
        if path == "/brackets":
            return self.send(200, "text/plain; charset=utf-8", b"[" * (1024 * 1024) + b" tail")
        if path == "/cancel-slow":
            if reader:
                return html("<html><body></body></html>")
            return html("<html><body><script>fetch('/data?ms=8000&text=late')</script></body></html>")
        # Fake engines: localhost:<port> is the search host; targets live on 127.0.0.1:<port>.
        if path == "/google/search":
            scenario = query.get("scenario")
            if scenario == "429":
                return html("<p>Too many requests</p>", 429)
            if scenario == "sorry":
                return self.send(302, None, b"", Location="/sorry/index?continue=x")
            if scenario == "results":
                links = "".join(f'<div><a href="/goto?k={k}"><h3>Google {k}</h3></a><div class="VwiC3b">snippet {k}</div></div>' for k in ("js", "302pdf", "stay"))
                return html(f'<html><body><div id="search"><div id="rso">{links}</div></div></body></html>')
            return html('<html><body><div id="search"></div></body></html>')
        if path == "/sorry/index":
            return html("<p>Our systems have detected unusual traffic.</p>")
        if path == "/bing/search":
            if query.get("scenario") == "wrapped":
                items = "".join(f'<li class="b_algo"><h2><a href="http://localhost:{port}/bing/ck?k={k}">Bing {k}</a></h2><div class="b_caption"><p>snippet {k}</p></div></li>' for k in ("302hang", "302b"))
            else:
                items = "".join(f'<li class="b_algo"><h2><a href="{target(f"bing{i}")}">Bing {i}</a></h2><div class="b_caption"><p>Bing snippet {i}</p></div></li>' for i in (1, 2, 3))
            return html(f'<html><body><ol id="b_results">{items}</ol></body></html>')
        if path == "/goto":
            kind = query.get("k")
            if kind == "js":
                return html(f"<script>location.replace({json.dumps(target('a'))})</script>")
            if kind == "302pdf":
                return self.send(302, None, b"", Location=target("doc.pdf"))
            return html("<p>An intermediate page that needs a click.</p>")
        if path == "/bing/ck":
            return self.send(302, None, b"", Location=target("hang" if query.get("k") == "302hang" else "b"))
        if path == "/target/doc.pdf":
            return self.send(200, "application/pdf", PDF_SMALL)
        if path == "/target/hang":
            return self.hang()
        if path.startswith("/target/"):
            return html(f"<html><head><title>Target {path}</title></head><body><p>Target page {path}</p></body></html>")
        return html("<p>not found</p>", 404)


STOP = threading.Event()
SERVER = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
SERVER.daemon_threads = True
PORT = SERVER.server_address[1]
BASE = f"http://127.0.0.1:{PORT}"
threading.Thread(target=SERVER.serve_forever, daemon=True).start()


# ---------------------------------------------------------------- process forensics (same script)
def stat(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text[text.rindex(")") + 1:].split()
        return fields[0], int(fields[1]), int(fields[2]), fields[19], text[text.index("(") + 1:text.rindex(")")]
    except (OSError, ValueError, IndexError):
        return None


def descendants():
    table = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            record = stat(int(entry.name))
            if record:
                table[int(entry.name)] = record
    family, grew = {os.getpid()}, True
    while grew:
        grew = False
        for pid, record in table.items():
            if pid not in family and record[1] in family:
                family.add(pid)
                grew = True
    family.discard(os.getpid())
    return {pid: table[pid] for pid in family}


class Forensics:
    def __init__(self, ignore=()):
        self.ignore, self.seen, self.stop = set(ignore), {}, threading.Event()

    def __enter__(self):
        def sample():
            while not self.stop.is_set():
                for pid, (_state, _ppid, group, started, comm) in descendants().items():
                    if pid not in self.ignore:
                        self.seen.setdefault((pid, started), {"pid": pid, "pgid": group, "comm": comm})
                time.sleep(0.05)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def finish(self):
        self.stop.set()
        self.thread.join()
        time.sleep(0.5)
        survivors = []
        for (pid, started), info in self.seen.items():
            now = stat(pid)
            if now and now[3] == started and now[0] != "Z":
                survivors.append(info)
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        comms = sorted({info["comm"] for info in self.seen.values()})
        return {"processes_seen": len(self.seen), "commands_seen": comms, "survivors": survivors}

    def __exit__(self, *_exc):
        if not self.stop.is_set():
            self.stop.set()


# ---------------------------------------------------------------- product entry helpers
PRELOAD = HERE / "preload.mjs"


def custom(query: dict | None = None, command=None, args=None):
    """Environment for the product's custom-command path."""
    if command is None:
        url = PRELOAD.as_uri() + ("?" + "&".join(f"{k}={quote(str(v), safe='')}" for k, v in query.items()) if query else "")
        command, args = NODE, ["--import", url, str(DIST)]
    return {"AGENT_MCP_WEB_SEARCH_COMMAND": command, "AGENT_MCP_WEB_SEARCH_ARGS": shlex.join(args)}


async def load(env=None, extra_specs=()):
    saved = {key: os.environ.get(key) for key in (env or {})}
    os.environ.update(env or {})
    try:
        diagnostics = []
        specs = [*mcp.resolve_mcp_specs(diagnostics=diagnostics), *extra_specs]
        begin = time.monotonic()
        tools, _families = await mcp.load_mcp_tools_with_families(specs=specs, diagnostics=diagnostics)
        return {tool.name: tool for tool in tools}, diagnostics, round((time.monotonic() - begin) * 1000)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def call(tools, name, args):
    begin = time.monotonic()
    try:
        response = await tools[name].ainvoke(args)
        text = response if isinstance(response, str) else "\n".join(part.get("text", "") for part in response)
        error = None
    except Exception as exc:  # the wrapper's own errors are facts too
        text, error = "", f"{type(exc).__name__}: {exc}"
    return {"ms": round((time.monotonic() - begin) * 1000), "text": text, "error": error}


def excerpt(text: str, limit=2000) -> str:
    return text.replace(BASE, "http://127.0.0.1:<port>").replace(f"localhost:{PORT}", "localhost:<port>")[:limit]


def line(text: str, prefix: str) -> str | None:
    return next((item for item in text.splitlines() if item.startswith(prefix)), None)


# ---------------------------------------------------------------- cases
CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


@case
async def c01_nested_tables(default):
    out = {}
    for depth in (3, 20):
        result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/nested/{depth}"})
        content = result["text"].split("**Page content:**", 1)[-1]
        out[f"depth_{depth}"] = {"ms": result["ms"], "leaf_count": content.count("LEAF"),
                                 "labels_once": all(content.count(f"L{level}x") == 1 for level in range(1, depth + 1))}
    checks = {f"depth {d}: each text once": out[f"depth_{d}"]["leaf_count"] == 1 and out[f"depth_{d}"]["labels_once"] for d in (3, 20)}
    return out, checks


@case
async def c02_whole_page(default):
    result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/articles"})
    content = result["text"].split("**Page content:**", 1)[-1]
    order = [content.find(word) for word in ("Intro", "Story 1", "Story 2", "Related", "Main", "Tail")]
    return {"order": order, "content": excerpt(content, 400)}, {"all text in source order": all(a >= 0 for a in order) and order == sorted(order)}


@case
async def c03_encodings(default):
    out, checks = {}, {}
    for route, word, encoding in (("big5", "中文", "Character encoding: big5 (Content-Type charset)"), ("sjis", "日本", "Character encoding: shift_jis (meta charset)")):
        result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/{route}"})
        out[route] = {"encoding_line": line(result["text"], "Character encoding:"), "has_text": word in result["text"]}
        checks[f"{route} decoded with visible source"] = out[route]["has_text"] and out[route]["encoding_line"] == encoding
    return out, checks


@case
async def c04_late_render(default):
    out, checks = {}, {}
    for name in ("timer300", "navfetch", "late5000"):
        result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/late/{name}"})
        text = result["text"]
        out[name] = {"ms": result["ms"], "status": line(text, "Page read status:"), "attempts": [l for l in text.splitlines() if l.startswith("- ")],
                     "read_error": line(text, "Read error:"), "target": "TARGET" in text.split("**Page content:**", 1)[-1] if "**Page content:**" in text else False}
    checks["timer 300 ms read"] = out["timer300"]["target"]
    checks["nav first, fetch 300 ms read"] = out["navfetch"]["target"]
    checks["5000 ms is empty_text with the waited time"] = (out["late5000"]["status"] or "").startswith("Page read status: empty_text") and "No visible text after waiting" in (out["late5000"]["read_error"] or "")
    return out, checks


@case
async def c05_browser_identity(default):
    result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/ua"})
    ua = line(result["text"], "UA: ")
    return {"echoed": ua, "attempts": [l for l in result["text"].splitlines() if l.startswith("- ")]}, {
        "fallback UA is a normal Chrome UA": bool(ua) and "Headless" not in ua and "Chrome/" in ua}


@case
async def c06_slow_drip(default):
    result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/drip"})
    attempts = [l for l in result["text"].splitlines() if l.startswith("- ")]
    return {"ms": result["ms"], "status": line(result["text"], "Page read status:"), "attempts": attempts}, {
        "HTTP ends at its operation limit": any("operation limit" in a for a in attempts if a.startswith("- http")),
        "fallback ran": any(a.startswith("- browser") for a in attempts),
        "far below the 285 s call budget": result["ms"] < 30000}


@case
async def c07_media_and_downloads(default):
    out = {}
    for route in ("big.pdf", "big.html", "deny-pdf"):
        result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/{route}"})
        text = result["text"]
        out[route] = {"status": line(text, "Page read status:"), "http": line(text, "HTTP status:"), "read_error": line(text, "Read error:"),
                      "attempts": [l for l in text.splitlines() if l.startswith("- ")]}
    checks = {
        "11 MiB PDF is unsupported_media with headers": out["big.pdf"]["status"].startswith("Page read status: unsupported_media") and out["big.pdf"]["http"] == "HTTP status: 200; Content-Type: application/pdf",
        "11 MiB HTML is http_error with the read limit": out["big.html"]["status"].startswith("Page read status: http_error") and "response body exceeds 10 MiB read limit" in (out["big.html"]["read_error"] or ""),
        "403 then browser PDF is unsupported_media (AF10b)": out["deny-pdf"]["status"].startswith("Page read status: unsupported_media") and "application/pdf" in out["deny-pdf"]["http"] and any(a.startswith("- http: status=403") for a in out["deny-pdf"]["attempts"]),
        "error lines are single lines": all("\n" not in (v["read_error"] or "") for v in out.values()),
    }
    return out, checks


@case
async def c08_full_search_statistics(_default):
    tools, diagnostics, _ms = await load(custom({"mode": "stub", "base": BASE, "count": 10}))
    before = len([e for e in LOG if e["path"].startswith("/slow/")])
    result = await call(tools, "full-web-search", {"query": "stub statistics", "limit": 10})
    reads = len([e for e in LOG if e["path"].startswith("/slow/")]) - before
    text = result["text"]
    stats = line(text, "Read statistics:")
    return {"ms": result["ms"], "engines": [l for l in text.splitlines() if l.startswith("- Google") or l.startswith("- Bing")],
            "stats": stats, "scope_line": line(text, "Statistics scope:"), "server_reads": reads, "diagnostics": diagnostics,
            "note": "custom command: node --import preload.mjs?mode=stub <dist>/index.js (product loader, wrapper and allowlist)"}, {
        "all 10 read": text.count("Read status: text") == 10,
        "no page window timeout": "page read window" not in text,
        "statistics equal server events": f"source_read_attempts={reads}; http_attempts={reads}; browser_attempts=0" in (stats or "") and reads == 10,
        "scope line present": bool(line(text, "Statistics scope:")),
    }


def engines_env(google, bing, link_resolve=None):
    query = {"mode": "engines", "google": f"http://localhost:{PORT}/google/search?scenario={google}",
             "bing": f"http://localhost:{PORT}/bing/search?scenario={bing}", "host": f"localhost:{PORT}"}
    if link_resolve:
        query["linkResolve"] = link_resolve
    return custom(query)


@case
async def c09_engine_fallback(_default):
    out, checks = {}, {}
    for scenario in ("429", "sorry"):
        tools, _diag, _ms = await load(engines_env(scenario, "fill"))
        result = await call(tools, "get-web-search-summaries", {"query": "fallback probe", "limit": 3})
        engines = [l for l in result["text"].splitlines() if l.startswith("- Google") or l.startswith("- Bing")]
        out[scenario] = {"engines": [excerpt(l) for l in engines], "candidates": line(result["text"], "Search for")}
        google = engines[0] if engines else ""
        checks[f"Google {scenario}: Bing fills"] = "status=completed" in (engines[1] if len(engines) > 1 else "") and "3 candidates" in (out[scenario]["candidates"] or "")
        checks[f"Google {scenario}: facts on the engine line"] = ("http_status=429" in google) if scenario == "429" else ("final_path=/sorry/index" in google)
    params = {}
    for query in ("颱風 消息", "typhoon news"):
        tools, _diag, _ms = await load(engines_env("params", "fill"))
        mark = len(LOG)
        await call(tools, "get-web-search-summaries", {"query": query, "limit": 2})
        seen = {e["path"]: e["query"] for e in LOG[mark:] if e["path"] in ("/google/search", "/bing/search")}
        params[query] = {"google_hl": seen.get("/google/search", {}).get("hl"), "bing_setlang": seen.get("/bing/search", {}).get("setlang"),
                         "bing_cc": seen.get("/bing/search", {}).get("cc")}
    out["market"] = params
    checks["market by query language"] = params["颱風 消息"] == {"google_hl": "zh-TW", "bing_setlang": "zh-Hant", "bing_cc": "TW"} and params["typhoon news"] == {"google_hl": "en", "bing_setlang": "en", "bing_cc": "US"}
    out["note"] = "custom command: node --import preload.mjs?mode=engines (real Google/Bing methods on fake engine pages)"
    return out, checks


@case
async def c10_link_resolution(_default):
    tools, _diag, _ms = await load(engines_env("results", "wrapped", 2000))
    mark = len(LOG)
    result = await call(tools, "full-web-search", {"query": "resolution probe", "limit": 5, "maxContentLength": 300})
    text = result["text"]
    blocks = text.split("\n\n**")[1:]
    rows = []
    for block in blocks:
        rows.append({"title": block.split("**", 1)[0], "url": excerpt(line(block, "URL: ") or ""), "link": excerpt(line(block, "Link: ") or ""),
                     "read_status": line(block, "Read status:"), "final_url": excerpt(line(block, "Final URL:") or "")})
    reads = [(e["path"], e["query"].get("k")) for e in LOG[mark:] if e["http_reader"]]
    by_title = {row["title"].split(": ", 1)[-1]: row for row in rows}
    ms = lambda title: int(by_title[title]["link"].rsplit(" in ", 1)[-1].split(" ")[0]) if " in " in by_title.get(title, {}).get("link", "") else None
    checks = {
        "JS redirect resolved": by_title.get("Google js", {}).get("url", "").endswith("/target/a"),
        "302 to PDF resolved quickly": by_title.get("Google 302pdf", {}).get("url", "").endswith("/target/doc.pdf") and (ms("Google 302pdf") or 9999) < 1000,
        "302 to a silent target resolved quickly": by_title.get("Bing 302hang", {}).get("url", "").endswith("/target/hang") and (ms("Bing 302hang") or 9999) < 1000,
        "no redirect is stayed_on_engine_host": "stayed_on_engine_host" in by_title.get("Google stay", {}).get("link", ""),
        # Only the unresolved (stayed) wrapper is read at its own address.
        "page reads use resolved URLs": ("/target/a", None) in reads and ("/target/b", None) in reads
            and [k for p, k in reads if p in ("/goto", "/bing/ck")] == ["stay"],
    }
    return {"ms": result["ms"], "rows": rows, "http_reader_paths": reads, "stats": line(text, "Read statistics:"),
            "note": "custom command: node --import preload.mjs?mode=engines&linkResolve=2000; real full Chromium"}, checks


@case
async def c11_odd_process_name(_default):
    binary = SCRATCH / "a) b c d"
    shutil.copy("/bin/sleep", binary)
    sleeper = subprocess.Popen([str(binary), "60"])
    try:
        tools, diagnostics, ms = await load()
        result = await call(tools, "get-single-web-page-content", {"url": f"{BASE}/articles"}) if tools else {"text": "", "error": "no tools"}
        return {"comm": stat(sleeper.pid)[4], "discovery_ms": ms, "diagnostics": diagnostics, "status": line(result["text"], "Page read status:")}, {
            "discovery and call work": bool(tools) and (line(result["text"], "Page read status:") or "").startswith("Page read status: text")}
    finally:
        sleeper.kill()
        sleeper.wait()


@case
async def c12_cancel_with_chromium(default):
    loop = asyncio.get_running_loop()
    handler_messages = []
    loop.set_exception_handler(lambda _loop, context: handler_messages.append(str(context.get("message"))))
    mark = len(captured)
    task = asyncio.create_task(call(default, "get-single-web-page-content", {"url": f"{BASE}/cancel-slow"}))
    began = time.monotonic()
    while time.monotonic() - began < 15 and not any("chrome" in r[4] for r in descendants().values()):
        await asyncio.sleep(0.05)
    chromium_seen = any("chrome" in r[4] for r in descendants().values())
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
        cancelled = False
    except asyncio.CancelledError:
        cancelled = True
    gc.collect()
    await asyncio.sleep(1)
    gc.collect()
    logs = captured[mark:]
    never = [m for m in [*logs, *handler_messages] if "never retrieved" in m]
    return {"chromium_running_at_cancel": chromium_seen, "cancelled": cancelled, "never_retrieved": never[:3]}, {
        "Chromium was running": chromium_seen, "caller cancelled": cancelled, "no 'never retrieved'": not never}


@case
async def c13_timeout_and_load_diagnostics(_default):
    helper = HERE / "mcp_helper.py"
    tools, _diag, _ms = await load({**custom(command=sys.executable, args=[str(helper), "hang_call"]), "DEFAULT_TIMEOUT": "3000"})
    result = await call(tools, "get-single-web-page-content", {"url": f"{BASE}/articles"})
    tools2, diagnostics, _ms2 = await load(custom(command=sys.executable, args=["-c", "import sys; sys.exit(3)"]))
    detail = next((d for d in diagnostics if d.startswith("mcp:web_search")), "")
    log_path = str(SCRATCH / "cache/agent-mcp/web_search.stderr.log")
    return {"timeout_ms": result["ms"], "timeout_error": result["error"], "load_diagnostic": detail.replace(str(SCRATCH), "<scratch>")}, {
        "timeout names the budget": "DEFAULT_TIMEOUT=3000 ms" in (result["error"] or "") and result["ms"] < 3500,
        "load failure names the leaf and log": not tools2 and "[causes: McpError: Connection closed]" in detail and detail.endswith(f"stderr log: {log_path}"),
    }


@case
async def c14_startup_cap(_default):
    healthy = mcp.MCPServerSpec("other", sys.executable, [str(HERE / "mcp_helper.py"), "healthy"], {}, sanitize_stdout=False)
    tools, diagnostics, ms = await load(custom(command="/bin/sleep", args=["120"]), extra_specs=[healthy])
    detail = next((d for d in diagnostics if d.startswith("mcp:web_search")), "")
    return {"load_ms": ms, "tools": sorted(tools), "diagnostic": detail.replace(str(SCRATCH), "<scratch>")}, {
        "gives up within about 15 s": 14000 <= ms < 20000,
        "diagnostic names the cap and the log": "startup timeout (15000 ms)" in detail and "stderr log:" in detail,
        "other servers still load": list(tools) == ["local_probe"],
    }


@case
async def c15_adversarial_plain_text(default):
    result = await call(default, "get-single-web-page-content", {"url": f"{BASE}/brackets"})
    return {"ms": result["ms"], "status": line(result["text"], "Page read status:"), "length": line(result["text"], "Markdown length:")}, {
        "returns text": (line(result["text"], "Page read status:") or "").startswith("Page read status: text"),
        "returns quickly": result["ms"] < 10000,
    }


async def main():
    out = {"dist": str(DIST.relative_to(REPO)), "node": NODE and Path(NODE).name, "port_note": "<port> replaces the local server port", "cases": {}}
    default, diagnostics, ms = await load()
    out["default_load"] = {"tools": sorted(default), "diagnostics": diagnostics, "ms": ms}
    for name, fn in CASES.items():
        if ONLY and name not in ONLY:
            continue
        forensics = Forensics()
        with forensics:
            begin = time.monotonic()
            try:
                facts, checks = await fn(default)
            except Exception as exc:  # recorded as a failed case, never as a pass
                facts, checks = {"exception": f"{type(exc).__name__}: {exc}"}, {"case ran": False}
            elapsed = round((time.monotonic() - begin) * 1000)
        processes = forensics.finish()
        checks["no surviving processes"] = not processes["survivors"]
        out["cases"][name] = {"pass": all(checks.values()), "checks": checks, "ms": elapsed, "facts": facts, "processes": processes}
        print(f"{name}: {'pass' if all(checks.values()) else 'FAIL'} {json.dumps(checks, ensure_ascii=False)}", flush=True)
    STOP.set()
    SERVER.shutdown()
    text = json.dumps(out, ensure_ascii=False, indent=1).replace(BASE, "http://127.0.0.1:<port>").replace(f"localhost:{PORT}", "localhost:<port>").replace(str(SCRATCH), "<scratch>")
    (HERE / "results.json").write_text(text + "\n")
    print(json.dumps({name: case["pass"] for name, case in out["cases"].items()}), flush=True)


asyncio.run(main())
