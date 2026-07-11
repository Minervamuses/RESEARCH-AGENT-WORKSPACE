"""Conservative natural-language confirmation decisions."""

import pytest

from skills.citation.confirmation import classify_confirmation
from skills.citation.types import CitationMatch


def _match(match_id: str) -> CitationMatch:
    return CitationMatch(
        match_id=match_id,
        candidate_id="c1",
        canonical_doi=f"10.1234/{match_id}",
    )


@pytest.mark.parametrize("phrase", [
    "儲存", "保存", "確認", "可以", "要這篇", "就這篇",
    "OK", "okay", "yes", "confirm", "save", "save it", "this one",
    "請幫我儲存，謝謝", "please save it",
])
def test_unique_match_accepts_conservative_approval_phrases(phrase):
    decision = classify_confirmation(phrase, [_match("m1")])
    assert decision.approved
    assert decision.match_id == "m1"


@pytest.mark.parametrize("phrase", [
    "不要儲存", "先別確認", "取消", "no", "do not save", "don't confirm",
])
def test_negation_always_refuses(phrase):
    decision = classify_confirmation(phrase, [_match("m1")])
    assert decision.status == "rejected"


@pytest.mark.parametrize("phrase", [
    "可以嗎？", "能不能儲存", "can you save it?", "where was this saved?",
    "我想知道儲存在哪裡",
])
def test_questions_and_non_approval_prose_never_confirm(phrase):
    decision = classify_confirmation(phrase, [_match("m1")])
    assert not decision.approved


def test_multiple_matches_require_one_live_match_id():
    matches = [_match("m1"), _match("m2")]
    assert classify_confirmation("就這篇", matches).status == "ambiguous"
    approved = classify_confirmation("確認 m2", matches)
    assert approved.approved and approved.match_id == "m2"
    assert classify_confirmation("確認 m1 m2", matches).status == "ambiguous"
    assert classify_confirmation("確認 m9", matches).status == "rejected"


def test_requested_tool_identifier_must_match_user_text():
    decision = classify_confirmation(
        "確認 m2", [_match("m1"), _match("m2")], requested_match_id="m1"
    )
    assert decision.status == "rejected"
