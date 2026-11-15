"""The @grill evaluation framework: case format, offline runner and reports (K6)."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent
EXAMPLE_CASES = APP / "tests" / "fixtures" / "grill" / "cases.example.json"


def _load_script():
    spec = importlib.util.spec_from_file_location("grill_eval", APP / "scripts" / "grill_eval.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["grill_eval"] = module
    spec.loader.exec_module(module)
    return module


grill_eval = _load_script()


def _example() -> dict:
    return json.loads(EXAMPLE_CASES.read_text(encoding="utf-8"))


def test_example_cases_pass_the_format_check():
    cases = grill_eval.load_cases(EXAMPLE_CASES)
    assert [case["kind"] for case in cases].count("flawed") >= 3
    assert [case["kind"] for case in cases].count("clean") >= 2
    assert {case["source"] for case in cases} == {"synthetic"}
    assert "示範用" in _example()["note"] and "不能代表真實論文" in _example()["note"]


@pytest.mark.parametrize("mutate,message", [
    (lambda case: case.update(selection="不存在於文件中的段落"), "selection does not occur verbatim"),
    (lambda case: case.update(kind="clean"), "kind 'clean' but lists known_issues"),
    (lambda case: case.update(known_issues=[]), "kind 'flawed' but lists no known_issues"),
    (lambda case: case["author_turns"][0].update(type="insist"), "type must be one of rephrase, supply_step, valid_rebuttal"),
    (lambda case: case["author_turns"][0].update(expected="withdraw"), "expected must be 'request_write_in' for type 'supply_step'"),
    (lambda case: case["known_issues"][0].update(quote="不在文件裡"), "quote does not occur verbatim"),
    (lambda case: case.update(kind="maybe"), "kind must be one of flawed, clean"),
    (lambda case: case.update(source="thesis"), "source must be one of synthetic, real"),
    (lambda case: case.update(extra=1), "unknown field(s) extra"),
    (lambda case: case.pop("author_turns"), "missing author_turns"),
])
def test_malformed_cases_are_rejected_with_clear_messages(mutate, message):
    data = _example()
    case = data["cases"][0]
    mutate(case)
    with pytest.raises(grill_eval.CaseFormatError, match=__import__("re").escape(message)) as error:
        grill_eval.validate_cases(data)
    assert "flawed-inference-gap" in str(error.value)


def test_duplicate_ids_and_repeated_selection_are_rejected():
    data = _example()
    data["cases"].append(copy.deepcopy(data["cases"][0]))
    with pytest.raises(grill_eval.CaseFormatError, match="case ids repeat: flawed-inference-gap"):
        grill_eval.validate_cases(data)
    data = _example()
    case = data["cases"][0]
    case["document"] += "\n" + case["selection"] + "\n"
    with pytest.raises(grill_eval.CaseFormatError, match="occurs 2 times"):
        grill_eval.validate_cases(data)
