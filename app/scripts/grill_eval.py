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

import json
from pathlib import Path

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
