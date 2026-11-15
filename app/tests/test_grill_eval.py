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


from langchain_core.messages import AIMessage, HumanMessage


class _ScriptedGrill:
    """Offline model returning fixed replies per round and recording each prompt."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self.invoke(messages)

    def invoke(self, messages):
        self.prompts.append(next(m.content for m in reversed(messages) if isinstance(m, HumanMessage)))
        return AIMessage(content=self.replies.pop(0))


FLAWED_ROUND_1 = """## 還原
作者由兩班平均成績的差異，推論同儕互評能提升所有學生的寫作能力。

## 發現
### F1｜問題
- 原文：「因此，同儕互評能提升所有學生的寫作能力。」
- 理由：平均提升不代表每位學生都提升。
- 請回應：是否有個別學生的資料？

### F2｜資料不足
- 原文：「實驗班平均提升了六分」
- 理由：前測未報告。
- 請回應：請提供前測。

## 判斷
判斷：待回應
"""
FLAWED_LATER = """## 還原
同上。

## 回應檢查
- F1：對題 → 請寫進文字：作者有逐一檢查的資料。

## 發現
### F2｜資料不足
- 原文：「兩班並非隨機分派，且前測成績未報告。」
- 理由：前測仍未報告。
- 請回應：請提供前測。

## 判斷
判斷：資料不足
"""
CLEAN_PASS = """## 還原
在此樣本與作業條件下，提示卡與較高平均正確率有關，並限定未檢驗其他族群。

## 發現
（無）

## 判斷
判斷：通過
在目前材料與檢查範圍內未找到具體問題。
"""
CLEAN_GAP = """## 還原
回訪比例上升，作者未宣稱因果。

## 發現
### F1｜資料不足
- 原文：「回訪比例由 41% 增加到 47%」
- 理由：需要「回訪」的定義才能判斷。
- 請回應：回訪如何定義？

## 判斷
判斷：資料不足
"""


def _scripted_factory(models):
    replies = {
        "flawed-inference-gap": [FLAWED_ROUND_1, FLAWED_LATER, FLAWED_LATER],
        "flawed-assumption-as-fact": [FLAWED_ROUND_1, FLAWED_LATER],
        "flawed-misapplied-concept": [FLAWED_ROUND_1, FLAWED_LATER],
        "clean-qualified-claim": [CLEAN_PASS],
        "clean-definition-from-context": [CLEAN_GAP, CLEAN_PASS],
    }

    def factory(case):
        models[case["id"]] = _ScriptedGrill(replies[case["id"]])
        return models[case["id"]]
    return factory


@pytest.fixture
def no_real_model(monkeypatch):
    """Fail loudly if anything tries to build an OpenRouter client."""
    created = []

    def refuse(*args, **kwargs):
        created.append(args)
        raise AssertionError("a real model client was requested")

    monkeypatch.setattr("agent.graph.get_chat_model", refuse)
    monkeypatch.setattr("agent.llm.openrouter.get_chat_model", refuse)
    monkeypatch.setattr("agent.session.get_chat_model_for_role", refuse)
    return created


def test_without_live_the_script_refuses_and_builds_no_model(tmp_path, no_real_model, capsys):
    out = tmp_path / "out"
    assert grill_eval.main(["--cases", str(EXAMPLE_CASES), "--out", str(out)]) == 2
    assert "refusing to run" in capsys.readouterr().err
    assert grill_eval.main(["--cases", str(EXAMPLE_CASES), "--out", str(out), "--dry-run", "--mcp"]) == 2
    assert no_real_model == [] and not out.exists()


def test_offline_run_records_format_rounds_and_read_only_document(tmp_path, no_real_model, capsys):
    out = tmp_path / "out"
    case_bytes = EXAMPLE_CASES.read_bytes()
    models = {}
    assert grill_eval.main(
        ["--cases", str(EXAMPLE_CASES), "--out", str(out), "--max-rounds", "4"],
        model_factory=_scripted_factory(models),
    ) == 0
    assert "MCP disabled" in capsys.readouterr().out
    assert no_real_model == [] and EXAMPLE_CASES.read_bytes() == case_bytes
    reports = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in (out / "reports").glob("*.json")}
    assert len(reports) == 5

    flawed = reports["flawed-inference-gap"]
    assert flawed["mcp_enabled"] is False and flawed["mode"] == "offline"
    assert flawed["rounds_run"] == flawed["rounds_planned"] == 3
    first = flawed["rounds"][0]["mechanical"]
    assert first["has_reconstruction"] is True and first["verdict"] == "待回應"
    f1, f2 = first["findings"]
    assert (f1["id"], f1["label"], f1["quote_verbatim_in_selection"]) == ("F1", "問題", True)
    assert (f2["id"], f2["label"], f2["quote_verbatim_in_document"]) == ("F2", "資料不足", False)
    later = flawed["rounds"][1]["mechanical"]
    assert later["response_checks"] == ["F1：對題 → 請寫進文字：作者有逐一檢查的資料。"]
    assert later["findings"][0]["quote_verbatim_in_document"] is True
    # Author replies were sent in order, each with @grill.
    prompts = models["flawed-inference-gap"].prompts
    case = grill_eval.load_cases(EXAMPLE_CASES)[0]
    assert [prompt.split("\n\n[Current editor", 1)[0] for prompt in prompts] == [
        grill_eval.FIRST_PROMPT, *(f"@grill {turn['text']}" for turn in case["author_turns"]),
    ]
    assert all(report["summary"]["document_edit_called"] is False for report in reports.values())
    assert all(report["summary"]["document_unchanged"] is True for report in reports.values())
    assert all(report["error"] is None for report in reports.values())

    clean = reports["clean-qualified-claim"]
    assert clean["summary"]["first_pass_round"] == 1 and clean["rounds"][0]["mechanical"]["declares_no_findings"]
    gap = reports["clean-definition-from-context"]
    assert gap["summary"]["verdicts"] == ["資料不足", "通過"] and gap["summary"]["first_pass_round"] == 2
    # A data-gap reply is recorded as such; nothing labels it a research failure or scores it.
    flat = json.dumps(reports, ensure_ascii=False)
    for word in ("score", "failure", "semantic", "\"pass\"", "correct"):
        assert word not in flat

    observations = flawed["observations"]
    assert [item["applicability"] for item in observations["author_turns"]] == ["待填", "待填"]
    assert all(item["faithful"] is None for item in observations["reconstruction"])
    assert [item["finding"] for item in observations["challenges"]] == ["F1", "F2", "F2", "F2"]
    assert [item["found"] for item in observations["known_issues"]] == [None]
    grill_eval.validate_observations(observations)

    markdown = (out / "reports" / "flawed-inference-gap.md").read_text(encoding="utf-8")
    assert "人工觀察" in markdown and "此輪不適用" in markdown and "條件式預期：request_write_in（僅在回應對題時適用）" in markdown
    assert "沒有品質分數" in (out / "summary.md").read_text(encoding="utf-8")


def test_filled_observations_can_mark_inapplicable_rounds_and_unlabeled_issues(tmp_path, no_real_model):
    out = tmp_path / "out"
    cases = grill_eval.load_cases(EXAMPLE_CASES)[:1]
    models = {}
    [report] = __import__("asyncio").run(grill_eval.run_cases(cases, out, model_factory=_scripted_factory(models)))
    filled = report["observations"]
    filled["reconstruction"][0].update(faithful="部分", notes="漏了「對照班提升 1 分」")
    filled["challenges"][0].update(valid="成立")
    filled["known_issues"][0].update(found="找到")
    filled["author_turns"][0].update(applicability="適用", reason="針對 F1", handling="合理")
    filled["author_turns"][1].update(applicability="此輪不適用", reason="模型已改要求寫進文字，腳本回應仍在爭論原質疑")
    filled["unlabeled_valid_issues"].append({"quote": "兩班由同一位教師授課", "note": "教師效應未討論"})
    grill_eval.validate_observations(filled)
    report["observations"] = filled
    markdown = grill_eval.render_case_markdown(report)
    assert "此輪不適用 | 模型已改要求寫進文字" in markdown and "教師效應未討論" in markdown

    for change, message in [
        (lambda o: o["author_turns"][1].update(reason=""), "needs a reason"),
        (lambda o: o["author_turns"][1].update(handling="合理"), "only when the reply applies"),
        (lambda o: o["challenges"][0].update(valid="很好"), "must be one of"),
        (lambda o: o["unlabeled_valid_issues"].append({"quote": "x"}), "quote and a note"),
    ]:
        broken = copy.deepcopy(filled)
        change(broken)
        with pytest.raises(ValueError, match=message):
            grill_eval.validate_observations(broken)
