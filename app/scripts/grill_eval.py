"""Offline-first evaluation runner for the @grill skill.

Run from ``app/`` in the Conda ``app`` environment::

    python scripts/grill_eval.py --cases CASES.json --out OUT_DIR --dry-run
    python scripts/grill_eval.py --cases CASES.json --out OUT_DIR --live

``--dry-run`` uses a built-in offline stand-in model and checks only the
pipeline. ``--live`` calls the configured OpenRouter model and costs money.
Without either flag the script refuses to run. See skills/grill/README.md.

Each case goes through the same desktop path as the editor: a temporary
project, the document opened, ``documentContext`` set to the selection, and
``@grill`` as an inline skill reference. Reports record what can be observed
mechanically and leave every research judgment to a human reader.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import shutil
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

CASE_KINDS = ("flawed", "clean")
CASE_SOURCES = ("synthetic", "real")
# Author reply type -> the conditional expectation it carries when the reply
# really answers the challenge raised. Whether it does is a human judgment.
RESPONSE_EXPECTATIONS = {
    "rephrase": "maintain",
    "supply_step": "request_write_in",
    "valid_rebuttal": "withdraw",
}
_CASE_KEYS = {"id", "kind", "source", "document", "selection", "known_issues", "author_turns"}
_ISSUE_KEYS = {"id", "quote", "note"}
_TURN_KEYS = {"targets", "type", "expected", "text"}


class CaseFormatError(ValueError):
    """A case file that does not follow the documented format."""


def _require_text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseFormatError(f"{where} must be a non-empty string")
    return value


def _check_keys(item: object, keys: set[str], where: str) -> dict:
    if not isinstance(item, dict):
        raise CaseFormatError(f"{where} must be an object")
    missing, extra = keys - item.keys(), item.keys() - keys
    if missing:
        raise CaseFormatError(f"{where} is missing {', '.join(sorted(missing))}")
    if extra:
        raise CaseFormatError(f"{where} has unknown field(s) {', '.join(sorted(extra))}")
    return item


def validate_case(case: object) -> dict:
    """Check one case and return it unchanged, or raise ``CaseFormatError``."""
    case_id = case.get("id") if isinstance(case, dict) else None
    where = f"case {case_id!r}" if isinstance(case_id, str) else "case"
    case = _check_keys(case, _CASE_KEYS, where)
    _require_text(case["id"], f"{where} id")
    if case["kind"] not in CASE_KINDS:
        raise CaseFormatError(f"{where} kind must be one of {', '.join(CASE_KINDS)}, not {case['kind']!r}")
    if case["source"] not in CASE_SOURCES:
        raise CaseFormatError(f"{where} source must be one of {', '.join(CASE_SOURCES)}, not {case['source']!r}")
    document = _require_text(case["document"], f"{where} document")
    selection = _require_text(case["selection"], f"{where} selection")
    occurrences = document.count(selection)
    if occurrences == 0:
        raise CaseFormatError(f"{where} selection does not occur verbatim in document")
    if occurrences > 1:
        raise CaseFormatError(f"{where} selection occurs {occurrences} times in document; make it unique")
    issues = case["known_issues"]
    if not isinstance(issues, list):
        raise CaseFormatError(f"{where} known_issues must be a list")
    if case["kind"] == "flawed" and not issues:
        raise CaseFormatError(f"{where} is kind 'flawed' but lists no known_issues")
    if case["kind"] == "clean" and issues:
        raise CaseFormatError(f"{where} is kind 'clean' but lists known_issues; use kind 'flawed'")
    seen: set[str] = set()
    for index, issue in enumerate(issues, start=1):
        issue_where = f"{where} known_issues[{index}]"
        issue = _check_keys(issue, _ISSUE_KEYS, issue_where)
        issue_id = _require_text(issue["id"], f"{issue_where} id")
        if issue_id in seen:
            raise CaseFormatError(f"{issue_where} repeats id {issue_id!r}")
        seen.add(issue_id)
        if _require_text(issue["quote"], f"{issue_where} quote") not in document:
            raise CaseFormatError(f"{issue_where} quote does not occur verbatim in document")
        _require_text(issue["note"], f"{issue_where} note")
    turns = case["author_turns"]
    if not isinstance(turns, list):
        raise CaseFormatError(f"{where} author_turns must be a list")
    for index, turn in enumerate(turns, start=1):
        turn_where = f"{where} author_turns[{index}]"
        turn = _check_keys(turn, _TURN_KEYS, turn_where)
        _require_text(turn["targets"], f"{turn_where} targets")
        _require_text(turn["text"], f"{turn_where} text")
        if turn["type"] not in RESPONSE_EXPECTATIONS:
            raise CaseFormatError(
                f"{turn_where} type must be one of {', '.join(RESPONSE_EXPECTATIONS)}, not {turn['type']!r}"
            )
        expected = RESPONSE_EXPECTATIONS[turn["type"]]
        if turn["expected"] != expected:
            raise CaseFormatError(
                f"{turn_where} expected must be {expected!r} for type {turn['type']!r}, not {turn['expected']!r}"
            )
    return case


def validate_cases(data: object) -> list[dict]:
    """Validate a whole case file (``{"note": ..., "cases": [...]}``)."""
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise CaseFormatError('case file must be an object with a "cases" list')
    if not data["cases"]:
        raise CaseFormatError("case file has no cases")
    cases = [validate_case(case) for case in data["cases"]]
    ids = [case["id"] for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise CaseFormatError(f"case ids repeat: {', '.join(duplicates)}")
    return cases


def load_cases(path: Path) -> list[dict]:
    """Read and validate a case file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaseFormatError(f"{path} is not valid JSON: {exc}") from exc
    return validate_cases(data)


# ---------------------------------------------------------------------------
# Mechanical record of one reply. These checks see only the visible format;
# they cannot show that a reconstruction is faithful or a challenge holds.

_FINDING = re.compile(r"^###\s*(F\d+)\s*｜\s*(問題|資料不足)\s*$", re.M)
_SECTION = re.compile(r"^##(?!#)\s*(\S.*?)\s*$", re.M)
_QUOTE = re.compile(r"原文：\s*「(.*?)」", re.S)
_VERDICT = re.compile(r"判斷：\s*(通過|待回應|資料不足)")
_CHECK_LINE = re.compile(r"^-\s*(F\d+)：\s*(.+)$", re.M)


def _sections(reply: str) -> dict[str, str]:
    marks = list(_SECTION.finditer(reply))
    return {
        match[1]: reply[match.end():marks[index + 1].start() if index + 1 < len(marks) else len(reply)]
        for index, match in enumerate(marks)
    }


def mechanical_record(reply: str, *, selection: str, document: str) -> dict[str, Any]:
    """What can be read off a reply's format, with no research judgment."""
    sections = _sections(reply)
    findings = []
    marks = list(_FINDING.finditer(reply))
    for index, match in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(reply)
        following = _SECTION.search(reply, match.end(), end)
        block = reply[match.end():following.start() if following else end]
        quote = _QUOTE.search(block)
        text = quote[1] if quote else None
        findings.append({
            "id": match[1], "label": match[2], "quote": text,
            "quote_verbatim_in_selection": text is not None and text in selection,
            "quote_verbatim_in_document": text is not None and text in document,
        })
    verdict = _VERDICT.search(reply)
    checks = sections.get("回應檢查", "")
    return {
        "has_reconstruction": "還原" in sections and bool(sections["還原"].strip()),
        "has_findings_section": "發現" in sections,
        "declares_no_findings": "（無）" in sections.get("發現", ""),
        "findings": findings,
        "verdict": verdict[1] if verdict else None,
        "response_checks": [f"{match[1]}：{match[2].strip()}" for match in _CHECK_LINE.finditer(checks)],
    }


# ---------------------------------------------------------------------------
# Human observation fields. Left blank by the script; filled by a reader.

APPLICABILITY = ("待填", "適用", "此輪不適用")
FAITHFUL = ("是", "部分", "否")
CHALLENGE = ("成立", "部分成立", "不成立", "無法判斷")
FOUND = ("找到", "部分", "未找到")
REASONABLE = ("合理", "部分合理", "不合理")


def blank_observations(case: dict, rounds: list[dict]) -> dict[str, Any]:
    """The human form for one case; every judgment starts empty."""
    return {
        "reconstruction": [
            {"round": record["round"], "faithful": None, "notes": ""} for record in rounds
        ],
        "challenges": [
            {"round": record["round"], "finding": finding["id"], "valid": None, "notes": ""}
            for record in rounds for finding in record["mechanical"]["findings"]
        ],
        "known_issues": [
            {"id": issue["id"], "found": None, "notes": ""} for issue in case["known_issues"]
        ],
        "unlabeled_valid_issues": [],
        "nitpicks": [],
        "author_turns": [
            {
                "round": index + 2, "applicability": "待填", "reason": "",
                "handling": None, "notes": "",
            }
            for index, _turn in enumerate(case["author_turns"]) if index + 2 <= len(rounds)
        ],
    }


def validate_observations(observations: dict) -> None:
    """Check a filled form uses the allowed values; raise ``ValueError`` otherwise."""
    def allowed(value, options, where):
        if value is not None and value not in options:
            raise ValueError(f"{where} must be one of {', '.join(options)} or empty, not {value!r}")

    for item in observations["reconstruction"]:
        allowed(item["faithful"], FAITHFUL, f"round {item['round']} reconstruction")
    for item in observations["challenges"]:
        allowed(item["valid"], CHALLENGE, f"round {item['round']} {item['finding']}")
    for item in observations["known_issues"]:
        allowed(item["found"], FOUND, f"known issue {item['id']}")
    for item in observations["author_turns"]:
        if item["applicability"] not in APPLICABILITY:
            raise ValueError(f"round {item['round']} applicability must be one of {', '.join(APPLICABILITY)}")
        if item["applicability"] == "此輪不適用" and not item["reason"].strip():
            raise ValueError(f"round {item['round']} marked 此輪不適用 needs a reason")
        if item["applicability"] != "適用" and item["handling"] is not None:
            raise ValueError(f"round {item['round']} handling is judged only when the reply applies")
        allowed(item["handling"], REASONABLE, f"round {item['round']} handling")
    for key in ("unlabeled_valid_issues", "nitpicks"):
        for item in observations[key]:
            if not isinstance(item, dict) or not str(item.get("quote", "")).strip() or not str(item.get("note", "")).strip():
                raise ValueError(f"{key} entries need a quote and a note")


# ---------------------------------------------------------------------------
# Running one case through the desktop document path.

FIRST_PROMPT = "@grill 請檢查選取的段落。"


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class _EventSink:
    """Collect turn events; refuse every approval so nothing runs with side effects."""

    def __init__(self, service, context):
        self.request_id = str(uuid.uuid4())
        self.service = service
        self.context = context
        self.events: list[tuple[str, dict]] = []
        self.tasks: list[asyncio.Task] = []

    def __call__(self, event, data):
        self.events.append((event, dict(data)))
        if event == "approval.required":
            self.tasks.append(asyncio.create_task(self.service.dispatch("approval.resolve", {
                "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                "turnId": data["turnId"], "approved": False, "documentContext": self.context,
            })))


@contextlib.contextmanager
def _patched(target: Any, name: str, value: Any) -> Iterator[None]:
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


async def run_case(
    case: dict, out_dir: Path, *, model: Any | None, load_mcp: bool = False, max_rounds: int = 4,
) -> dict[str, Any]:
    """Run one case: the first @grill check, then each scripted author reply.

    ``model`` is a chat model stand-in for offline runs; ``None`` uses the
    configured real model (only reached through ``--live``).
    """
    import agent.graph
    import agent.tools.inventory
    from agent.config import AgentConfig
    from agent.desktop.service import DesktopService, DesktopServiceError
    from agent.skills.runtime import resolve_skill_references

    work = out_dir / "work" / case["id"]
    if work.exists():
        shutil.rmtree(work)
    project = work / "project"
    project.mkdir(parents=True)
    document_path = project / "case.md"
    document_path.write_text(case["document"], encoding="utf-8")
    config = AgentConfig(
        persist_dir=str(work / "store"),
        extension_dropin_dir=str(work / "dropin"), extension_state_dir=str(work / "state"),
    )
    stack = contextlib.ExitStack()
    if model is not None:
        stack.enter_context(_patched(agent.graph, "get_chat_model", lambda _config: model))
        stack.enter_context(_patched(agent.tools.inventory, "create_rag_tools", lambda _config: []))
    rounds: list[dict[str, Any]] = []
    error = None
    with stack:
        service = DesktopService(original_cwd=project, config=config, approval_timeout_seconds=5.0)
        preview = await service.dispatch("workspace.select", {"rootPath": str(project), "action": "inspect"})
        opened_project = await service.dispatch("workspace.select", {
            "rootPath": str(project), "action": "initialize",
            "historyDirectory": preview["historyDirectory"],
            "expectedFingerprint": preview["researchFingerprint"],
        })
        await service.dispatch("session.create", {"loadMcp": load_mcp, "projectId": opened_project["projectId"]})
        diagnostics = await service.dispatch("runtime.diagnostics", {})
        opened = await service.dispatch("document.open", {"path": str(document_path)})
        before = document_path.read_bytes()
        start = _utf16(case["document"][:case["document"].index(case["selection"])])
        context = {**opened, "rangeStartUtf16": start, "rangeEndUtf16": start + _utf16(case["selection"])}
        prompts = [FIRST_PROMPT] + [f"@grill {turn['text']}" for turn in case["author_turns"]]
        for index, text in enumerate(prompts[:max(1, max_rounds)], start=1):
            sink = _EventSink(service, context)
            references = resolve_skill_references(text, service.session.loaded_skills)
            try:
                result = await service.dispatch("session.turn", {
                    "text": text, "turnId": uuid.uuid4().hex, "retry": False,
                    "documentContext": context, "skillReferences": references,
                }, event_sink=sink)
            except DesktopServiceError as exc:
                error = f"round {index}: {exc}"
                break
            finally:
                await asyncio.gather(*sink.tasks, return_exceptions=True)
            tools = [data["name"] for event, data in sink.events if event == "tool.started"]
            rounds.append({
                "round": index,
                "author_input": text,
                "author_turn": case["author_turns"][index - 2] if index > 1 else None,
                "reply": result["text"],
                "state": result["state"],
                "tools_called": tools,
                "tool_results": [
                    {"name": item["name"], "status": item["status"]} for item in result.get("toolSummaries", [])
                ],
                "approvals_refused": sum(event == "approval.required" for event, _data in sink.events),
                "document_proposals": sum(event == "document.proposed" for event, _data in sink.events),
                "mechanical": mechanical_record(result["text"], selection=case["selection"], document=case["document"]),
            })
        after = document_path.read_bytes()
    passes = [record["round"] for record in rounds if record["mechanical"]["verdict"] == "通過"]
    return {
        "case": {key: case[key] for key in ("id", "kind", "source", "selection", "known_issues")},
        "author_turns": case["author_turns"],
        "mode": "offline" if model is not None else "live",
        "mcp_enabled": bool(diagnostics.get("mcpEnabled")),
        "rounds_planned": len(prompts[:max(1, max_rounds)]),
        "rounds_run": len(rounds),
        "error": error,
        "rounds": rounds,
        "summary": {
            "first_pass_round": passes[0] if passes else None,
            "verdicts": [record["mechanical"]["verdict"] for record in rounds],
            "document_edit_called": any(
                "document_edit" in record["tools_called"] or record["document_proposals"] for record in rounds
            ),
            "document_unchanged": before == after == case["document"].encode("utf-8"),
        },
        "observations": blank_observations(case, rounds),
    }


# ---------------------------------------------------------------------------
# Reports.

_REPORT_NOTE = (
    "機械記錄只反映可觀察的格式與流程（有無還原段、引用是否逐字、如何表達判斷、有無編輯），"
    "不能證明模型理解原文或質疑成立；本報告沒有品質分數。kind 與 known_issues 是案例作者的標註，"
    "不是完整真值。作者回應的預期只有在回應確實針對模型實際提出的質疑時才適用，由閱讀者判斷。"
)


def _cell(value: object) -> str:
    if value is None:
        return "（待填）"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_case_markdown(report: dict) -> str:
    case, summary = report["case"], report["summary"]
    lines = [
        f"# 詰問評估：{case['id']}", "",
        f"> {_REPORT_NOTE}", "",
        f"- kind：{case['kind']}（案例作者標註）；source：{case['source']}",
        f"- 模式：{report['mode']}；MCP 啟用：{_cell(report['mcp_enabled'])}",
        f"- 執行輪數：{report['rounds_run']}／{report['rounds_planned']}" + (f"；中止：{report['error']}" if report["error"] else ""),
        f"- 首次宣告通過的輪次：{summary['first_pass_round'] or '未宣告（達上限或中止）'}",
        f"- 各輪判斷行：{'、'.join(str(item) for item in summary['verdicts']) or '—'}",
        f"- 全程有 document_edit 呼叫：{_cell(summary['document_edit_called'])}；文件未變：{_cell(summary['document_unchanged'])}",
        "", "## 選取段落", "", "```text", case["selection"], "```", "",
        "## 案例作者標註的已知問題", "",
    ]
    lines += [f"- {issue['id']}：「{issue['quote']}」— {issue['note']}" for issue in case["known_issues"]] or ["（無；clean 案例仍可能有其他有效問題）"]
    for record in report["rounds"]:
        mechanical = record["mechanical"]
        lines += ["", f"## 第 {record['round']} 輪", "", f"作者輸入：{record['author_input']}"]
        if record["author_turn"] is not None:
            turn = record["author_turn"]
            lines.append(
                f"腳本回應類型：{turn['type']}；預設回應的質疑：{turn['targets']}；"
                f"條件式預期：{turn['expected']}（僅在回應對題時適用）"
            )
        lines += [
            "", "模型回覆全文：", "", "````markdown", record["reply"], "````", "",
            f"呼叫的工具：{', '.join(record['tools_called']) or '無'}；被拒絕的核准：{record['approvals_refused']}",
            "", "| 機械記錄 | 值 |", "|---|---|",
            f"| 有還原段 | {_cell(mechanical['has_reconstruction'])} |",
            f"| 寫明無發現 | {_cell(mechanical['declares_no_findings'])} |",
            f"| 判斷行 | {_cell(mechanical['verdict'] or '未寫')} |",
        ]
        for finding in mechanical["findings"]:
            lines.append(
                f"| {finding['id']}（{finding['label']}）引用 | 「{_cell(finding['quote'] or '未附原文')}」；"
                f"逐字在選取段：{_cell(finding['quote_verbatim_in_selection'])}；"
                f"逐字在文件：{_cell(finding['quote_verbatim_in_document'])} |"
            )
        for check in mechanical["response_checks"]:
            lines.append(f"| 回應檢查 | {_cell(check)} |")
    observations = report["observations"]
    lines += ["", "## 人工觀察（由閱讀者填寫）", "",
              "| 輪次 | 還原是否忠於原文的限定與強度（是／部分／否） | 備註 |", "|---|---|---|"]
    lines += [f"| {item['round']} | {_cell(item['faithful'])} | {_cell(item['notes'])} |" for item in observations["reconstruction"]]
    lines += ["", "| 輪次 | 發現 | 質疑及理由是否成立（成立／部分成立／不成立／無法判斷） | 備註 |", "|---|---|---|---|"]
    lines += [f"| {item['round']} | {item['finding']} | {_cell(item['valid'])} | {_cell(item['notes'])} |" for item in observations["challenges"]] or ["| — | 無發現 | — | — |"]
    lines += ["", "| 已知問題 | 是否被找到（找到／部分／未找到） | 備註 |", "|---|---|---|"]
    lines += [f"| {item['id']} | {_cell(item['found'])} | {_cell(item['notes'])} |" for item in observations["known_issues"]] or ["| — | — | — |"]
    lines += ["", "| 輪次 | 作者回應是否針對實際質疑（適用／此輪不適用） | 理由 | 適用時，模型後續處理（合理／部分合理／不合理） | 備註 |", "|---|---|---|---|---|"]
    lines += [
        f"| {item['round']} | {item['applicability']} | {_cell(item['reason'] or None)} | {_cell(item['handling'])} | {_cell(item['notes'])} |"
        for item in observations["author_turns"]
    ] or ["| — | 無作者回應 | — | — | — |"]
    lines += ["", "標註之外的有效問題（引用＋說明）："]
    lines += [f"- 「{item['quote']}」— {item['note']}" for item in observations["unlabeled_valid_issues"]] or ["- （待填）"]
    lines += ["", "硬挑或不成立的質疑（引用＋說明）："]
    lines += [f"- 「{item['quote']}」— {item['note']}" for item in observations["nitpicks"]] or ["- （待填）"]
    return "\n".join(lines) + "\n"


def render_summary_markdown(reports: list[dict]) -> str:
    lines = [
        "# 詰問評估總表", "", f"> {_REPORT_NOTE}", "",
        "| 案例 | kind | source | 輪數 | 各輪有還原段 | 逐字引用／附引用的發現 | 各輪判斷行 | 首次宣告通過 | document_edit | 文件未變 | 中止 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for report in reports:
        rounds = report["rounds"]
        quoted = [finding for record in rounds for finding in record["mechanical"]["findings"] if finding["quote"]]
        verbatim = sum(finding["quote_verbatim_in_document"] for finding in quoted)
        lines.append(
            f"| {report['case']['id']} | {report['case']['kind']} | {report['case']['source']} | "
            f"{report['rounds_run']}/{report['rounds_planned']} | "
            f"{'、'.join(_cell(record['mechanical']['has_reconstruction']) for record in rounds) or '—'} | "
            f"{verbatim}/{len(quoted)} | "
            f"{'、'.join(_cell(record['mechanical']['verdict'] or '未寫') for record in rounds) or '—'} | "
            f"{report['summary']['first_pass_round'] or '—'} | "
            f"{_cell(report['summary']['document_edit_called'])} | {_cell(report['summary']['document_unchanged'])} | "
            f"{_cell(report['error'] or '—')} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(reports: list[dict], out_dir: Path) -> None:
    folder = out_dir / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    for report in reports:
        case_id = report["case"]["id"]
        (folder / f"{case_id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (folder / f"{case_id}.md").write_text(render_case_markdown(report), encoding="utf-8")
    (out_dir / "summary.md").write_text(render_summary_markdown(reports), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps([
        {"id": report["case"]["id"], "kind": report["case"]["kind"], "rounds_run": report["rounds_run"],
         "verdicts": report["summary"]["verdicts"], "first_pass_round": report["summary"]["first_pass_round"],
         "document_edit_called": report["summary"]["document_edit_called"],
         "document_unchanged": report["summary"]["document_unchanged"], "error": report["error"]}
        for report in reports
    ], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Offline stand-in model and command line.

class DryRunModel:
    """Offline stand-in: fixed, clearly labelled replies in the skill's format.

    It never reads the case's known issues and makes no judgment; it exists
    only so ``--dry-run`` exercises the real desktop path without a network.
    """

    def __init__(self, case: dict):
        self.quote = re.split(r"(?<=[。！？；])", case["selection"], maxsplit=1)[0]
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self.invoke(messages)

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        self.calls += 1
        follow_up = self.calls > 1
        reply = [
            "## 還原",
            f"（離線替身固定回覆，不是模型輸出）選取段落以「{self.quote}」開始。",
        ]
        if follow_up:
            reply += ["", "## 回應檢查", "- F1：未對題 → 維持：離線替身不判斷作者回應。"]
        reply += [
            "", "## 發現", "### F1｜資料不足", f"- 原文：「{self.quote}」",
            "- 理由：離線替身不檢查內容，只示範格式。", "- 請回應：無。",
            "", "## 判斷", "判斷：資料不足", "離線替身不做研究判斷。",
        ]
        return AIMessage(content="\n".join(reply))


ModelFactory = Callable[[dict], Any]


async def run_cases(
    cases: list[dict], out_dir: Path, *, model_factory: ModelFactory | None,
    load_mcp: bool = False, max_rounds: int = 4,
) -> list[dict]:
    reports = []
    for case in cases:
        model = model_factory(case) if model_factory is not None else None
        reports.append(await run_case(case, out_dir, model=model, load_mcp=load_mcp, max_rounds=max_rounds))
    write_reports(reports, out_dir)
    return reports


def planned_model_rounds(cases: list[dict], max_rounds: int) -> int:
    """Upper bound on @grill turns: per case 1 + author replies, capped by --max-rounds."""
    return sum(min(1 + len(case["author_turns"]), max(1, max_rounds)) for case in cases)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run @grill evaluation cases through the desktop document path.")
    parser.add_argument("--cases", type=Path, required=True, help="case file (JSON)")
    parser.add_argument("--out", type=Path, required=True, help="output directory for work files and reports")
    parser.add_argument("--max-rounds", type=int, default=4, help="most @grill turns per case (default 4)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="offline stand-in model; checks the pipeline only")
    mode.add_argument("--live", action="store_true", help="call the configured OpenRouter model (costs money)")
    parser.add_argument("--mcp", action="store_true", help="with --live, also load MCP servers such as web search")
    return parser


def main(argv: list[str] | None = None, *, model_factory: ModelFactory | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_cases(args.cases)
    except (CaseFormatError, OSError) as exc:
        print(f"grill_eval: {exc}", file=sys.stderr)
        return 2
    if not args.live and not args.dry_run and model_factory is None:
        print(
            "grill_eval: refusing to run without a mode. No real model is created unless --live is "
            "given (it calls OpenRouter and costs money). Use --dry-run to check the pipeline offline.",
            file=sys.stderr,
        )
        return 2
    if args.mcp and not args.live:
        print("grill_eval: --mcp is only meaningful with --live.", file=sys.stderr)
        return 2
    rounds = planned_model_rounds(cases, args.max_rounds)
    if args.live:
        factory = None
        print(f"grill_eval: LIVE run. {len(cases)} case(s), at most {rounds} @grill turn(s); each turn may make "
              "several model calls. This calls OpenRouter and will cost money.")
        print(f"grill_eval: MCP servers (web search) {'ENABLED' if args.mcp else 'disabled'}.")
    else:
        factory = model_factory or DryRunModel
        print(f"grill_eval: offline run with a stand-in model. {len(cases)} case(s), at most {rounds} turn(s). "
              "MCP disabled. Output shows the pipeline only, not research results.")
    args.out.mkdir(parents=True, exist_ok=True)
    reports = asyncio.run(run_cases(
        cases, args.out, model_factory=factory, load_mcp=bool(args.live and args.mcp), max_rounds=args.max_rounds,
    ))
    print(f"grill_eval: wrote {len(reports)} report(s) and summary.md under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
