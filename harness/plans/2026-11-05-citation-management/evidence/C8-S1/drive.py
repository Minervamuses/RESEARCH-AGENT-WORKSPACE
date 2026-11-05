"""C8-S1 end-to-end: drive the real desktop backend over NDJSON (no model calls).

Usage: python -I drive.py <work-dir> <evidence-dir>

Starts `python -m agent.desktop.server` the way the desktop host does (cwd =
repo root, PYTHONPATH = app/, CONDA_* = app) with every store redirected into
<work-dir>. No session is created and no session.turn is sent. The
citation.save approval that bibliography.add raises in Ask mode is answered by
this driver. Each public save request is appended to requests.jsonl before it
is sent; the plan's budget is 8 for the whole plan.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

REPO = Path("/home/minervamuses/research-agent-workspace")
PYTHON = "/home/minervamuses/miniconda3/envs/app/bin/python"
BUDGET = 8
DOI = "10.1038/s41586-021-03819-2"
ARXIV = "1706.03762"

work = Path(sys.argv[1]).resolve()
evidence = Path(sys.argv[2]).resolve()
project = work / "project"
for name in ("project", "store", "cite", "logs", "xdg", "history"):
    (work / name).mkdir(parents=True, exist_ok=True)

HAND_WRITTEN = [
    {"id": "fao2023faostat", "type": "webpage", "title": "FAOSTAT",
     "author": [{"literal": "Food and Agriculture Organization"}], "issued": {"date-parts": [[2023]]},
     "URL": "https://www.fao.org/faostat/", "accessed": {"date-parts": [[2026, 11, 5]]}},
    {"id": "old1999notes", "type": "report", "title": "Old field notes – never cited",
     "author": [{"family": "Old", "given": "Ann"}], "issued": {"date-parts": [[1999]]}, "publisher": "Lab"},
]
library = project / "references.json"
library.write_text(json.dumps(HAND_WRITTEN, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
hand_written_text = library.read_text(encoding="utf-8")
document = project / "draft.md"
document.write_text(
    "# Draft 🙂\n\nCrop statistics come from FAO [@fao2023faostat]. Protein structure prediction "
    "[@jumper2021highly] built on attention models [see @vaswani2017attention, p. 3].\n\n# References\n",
    encoding="utf-8",
)
document_hash = hashlib.sha256(document.read_bytes()).hexdigest()
repo_cite = REPO / "cite"
repo_cite_before = sorted(p.name for p in repo_cite.iterdir()) if repo_cite.is_dir() else None

requests_log = evidence / "requests.jsonl"
already = len(requests_log.read_text().splitlines()) if requests_log.exists() else 0
planned = 3
if already + planned > BUDGET:
    sys.exit(f"public request budget exceeded: {already} already sent, {planned} planned, budget {BUDGET}")

env = {
    "PATH": f"{Path(PYTHON).parent}:/usr/bin:/bin",
    "HOME": os.environ["HOME"],
    "PYTHONPATH": str(REPO / "app"),
    "CONDA_PREFIX": str(Path(PYTHON).parent.parent),
    "CONDA_DEFAULT_ENV": "app",
    "KMS_STORE_DIR": str(work / "store"),
    "CITATION_OUTPUT_DIR": str(work / "cite"),
    "AGENT_LOG_DIR": str(work / "logs"),
    "XDG_CACHE_HOME": str(work / "xdg"),
    "TMPDIR": os.environ.get("TMPDIR", str(work)),
}
for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy",
             "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS"):
    if name in os.environ:
        env[name] = os.environ[name]
server = subprocess.Popen(
    [PYTHON, "-m", "agent.desktop.server"], cwd=REPO, env=env,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
)
transcript = []


def trim(value):
    if isinstance(value, str):
        return value if len(value) <= 240 else value[:240] + f"…[{len(value)} chars]"
    if isinstance(value, list):
        return [trim(item) for item in value[:12]] + ([f"…[{len(value)} items]"] if len(value) > 12 else [])
    if isinstance(value, dict):
        return {key: trim(item) for key, item in value.items()}
    return value


def send(message):
    transcript.append({"dir": "send", "message": trim(message)})
    server.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    server.stdin.flush()


def read():
    line = server.stdout.readline()
    if not line:
        raise RuntimeError("backend closed stdout: " + server.stderr.read()[-2000:])
    message = json.loads(line)
    transcript.append({"dir": "recv", "message": trim(message)})
    return message


def call(method, params):
    request_id = str(uuid.uuid4())
    send({"protocolVersion": 1, "messageType": "request", "requestId": request_id, "method": method, "params": params})
    while True:
        message = read()
        if message.get("messageType") == "event" and message.get("requestId") == request_id \
                and message.get("event") == "approval.required":
            data = message["data"]
            assert data["operation"] == "citation.save", data
            send({"protocolVersion": 1, "messageType": "request", "requestId": str(uuid.uuid4()),
                  "method": "approval.resolve", "params": {
                      "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                      "turnId": data["turnId"], "approved": True}})
            continue
        if message.get("messageType") == "result" and message.get("requestId") == request_id:
            if not message.get("ok"):
                raise RuntimeError(f"{method} failed: {message.get('error')}")
            return message["data"]


def public_add(identifier):
    with requests_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "method": "bibliography.add",
                                 "identifier": identifier}) + "\n")
    return call("bibliography.add", {"identifier": identifier})


observations = {}
try:
    ready = read()
    assert ready.get("event") == "backend.ready", ready
    preview = call("workspace.select", {"rootPath": str(project), "action": "inspect",
                                        "historyDirectory": str(work / "history")})
    opened = call("workspace.select", {"rootPath": str(project), "action": "initialize",
                                       "historyDirectory": preview["historyDirectory"],
                                       "expectedFingerprint": preview["researchFingerprint"]})
    context = call("document.open", {"path": str(document)})
    before = call("bibliography.inspect", {"documentContext": context})
    observations["before"] = {"missing": before["missing"], "entries": [e["key"] for e in before["entries"]]}
    first = public_add(DOI)
    second = public_add(DOI)
    third = public_add(ARXIV)
    observations["adds"] = [first, second, third]
    after_add = call("bibliography.inspect", {"documentContext": context})
    observations["after_add"] = {
        "missing": after_add["missing"],
        "entries": [(e["key"], e["verification"], e["citedCount"]) for e in after_add["entries"]],
    }
    renders = {}
    for style in ("apa", "ieee", "bime-appendix17"):
        call("bibliography.set_style", {"styleId": style})
        renders[style] = call("bibliography.render", {"documentContext": context})
    observations["renders"] = {style: {"citations": [c["text"] for c in data["citations"]],
                                       "entries": [e["text"] for e in data["entries"]]}
                               for style, data in renders.items()}
    exports = {fmt: call("bibliography.export", {"documentContext": context, "format": fmt, "styleId": "ieee"})["path"]
               for fmt in ("docx", "markdown", "bib")}
    observations["exports"] = exports
    current = call("bibliography.inspect", {"documentContext": context})
    removed = call("bibliography.remove", {"key": "old1999notes", "libraryFingerprint": current["libraryFingerprint"]})
    final = call("bibliography.inspect", {"documentContext": context})
    observations["final"] = {"entries": [e["key"] for e in final["entries"]], "removed": removed["key"],
                             "styleId": final["styleId"], "styleConfigured": final["styleConfigured"]}
    call("runtime.shutdown", {})
finally:
    try:
        server.stdin.close()
    except OSError:
        pass
    try:
        server.wait(timeout=30)
    except subprocess.TimeoutExpired:
        server.kill()
    (evidence / "transcript.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in transcript) + "\n", encoding="utf-8")

# Checks on disk ------------------------------------------------------------------
data = json.loads(library.read_text(encoding="utf-8"))
checks = {
    "document_hash_unchanged": hashlib.sha256(document.read_bytes()).hexdigest() == document_hash,
    "hand_written_fao_unchanged": data[0] == HAND_WRITTEN[0],
    "library_only_appended_then_removed": [item["id"] for item in data] == ["fao2023faostat", "jumper2021highly", "vaswani2017attention"],
    "first_add_added": observations["adds"][0]["status"] == "added" and observations["adds"][0]["key"] == "jumper2021highly",
    "same_doi_existing": observations["adds"][1]["status"] == "existing" and observations["adds"][1]["key"] == "jumper2021highly",
    "arxiv_added": observations["adds"][2]["status"] == "added" and observations["adds"][2]["key"] == "vaswani2017attention",
    "no_missing_after_add": observations["after_add"]["missing"] == [],
    "apa_differs_from_ieee": observations["renders"]["apa"] != observations["renders"]["ieee"],
    "exports_exist": all(Path(path).is_file() for path in observations["exports"].values()),
    "docx_has_rendered_citation": "[1]" in zipfile.ZipFile(observations["exports"]["docx"]).read("word/document.xml").decode("utf-8"),
    "markdown_export_has_no_keys": "[@" not in Path(observations["exports"]["markdown"]).read_text(encoding="utf-8"),
    "removed_uncited_entry": observations["final"]["removed"] == "old1999notes" and "old1999notes" not in observations["final"]["entries"],
    "no_abstract_in_library": "abstract" not in library.read_text(encoding="utf-8").casefold(),
    "no_abstract_in_bundles": all("abstract" not in path.read_text(encoding="utf-8").casefold()
                                  for path in (work / "cite").glob("*/citation.json")),
    "bundles_in_temp_cite_only": len(list((work / "cite").glob("*/reference.bib"))) == 2,
    "repo_cite_untouched": (sorted(p.name for p in repo_cite.iterdir()) if repo_cite.is_dir() else None) == repo_cite_before,
}
appended = library.read_text(encoding="utf-8")
observations["checks"] = checks
observations["library_after"] = data
observations["hand_written_prefix_kept"] = appended.startswith(hand_written_text[: hand_written_text.index(' },\n {\n  "id": "old1999notes"')])
(evidence / "observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(checks, indent=1))
sys.exit(0 if all(checks.values()) else 1)
