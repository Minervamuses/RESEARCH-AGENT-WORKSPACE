"""Conservative natural-language approval for citation confirmation.

This module recognizes a deliberately small grammar. It never treats a mere
substring such as "where was this saved?" as approval, and negation/questions
win before any positive phrase is considered.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from skills.citation.types import CitationMatch

ConfirmationStatus = Literal["approved", "ambiguous", "rejected", "not_confirmation"]

_MATCH_ID_RE = re.compile(r"(?<![a-z0-9])m\d+(?![a-z0-9])", re.IGNORECASE)
_ENGLISH_NEGATION_RE = re.compile(
    r"(?:^|\s)(?:no|not|don['’]?t|do\s+not|cancel)(?:\s|$)", re.IGNORECASE
)
_ENGLISH_QUESTION_RE = re.compile(
    r"(?:^|\s)(?:can|could|would|should)\b", re.IGNORECASE
)
_CHINESE_NEGATIONS = ("不要", "先別", "別", "取消", "不")
_CHINESE_QUESTIONS = ("嗎", "么", "能不能", "可不可以")

_APPROVAL_CORES = {
    "儲存", "保存", "確認", "可以", "要這篇", "就這篇",
    "ok", "okay", "yes", "confirm", "save", "save it", "this one",
}
_LEADING_POLITE = ("請幫我", "麻煩", "請", "please")
_TRAILING_POLITE = ("謝謝", "thanks", "thank you", "please")


@dataclass(frozen=True)
class ConfirmationDecision:
    status: ConfirmationStatus
    match_id: str | None = None
    reason: str = ""

    @property
    def approved(self) -> bool:
        return self.status == "approved" and self.match_id is not None


def _normalized_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").casefold().strip()
    normalized = re.sub(r"[，,。.!！;；:：]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _strip_polite_wrappers(text: str) -> str:
    out = text.strip()
    changed = True
    while changed:
        changed = False
        for prefix in _LEADING_POLITE:
            if out.startswith(prefix):
                out = out[len(prefix):].strip()
                changed = True
                break
        for suffix in _TRAILING_POLITE:
            if out.endswith(suffix):
                out = out[:-len(suffix)].strip()
                changed = True
                break
    return out


def classify_confirmation(
    user_input: str,
    pending_matches: list[CitationMatch] | tuple[CitationMatch, ...],
    *,
    requested_match_id: str | None = None,
) -> ConfirmationDecision:
    """Classify explicit approval against the current live match set."""
    text = _normalized_text(user_input)
    live_ids = {match.match_id.casefold(): match.match_id for match in pending_matches}
    if not text or not live_ids:
        return ConfirmationDecision("not_confirmation", reason="no live matches")

    if (
        any(token in text for token in _CHINESE_NEGATIONS)
        or _ENGLISH_NEGATION_RE.search(text)
    ):
        return ConfirmationDecision("rejected", reason="negation or cancellation")
    if (
        "?" in text
        or "？" in text
        or any(token in text for token in _CHINESE_QUESTIONS)
        or _ENGLISH_QUESTION_RE.search(text)
    ):
        return ConfirmationDecision("ambiguous", reason="question or conditional wording")

    mentioned = [match.group(0).casefold() for match in _MATCH_ID_RE.finditer(text)]
    mentioned = list(dict.fromkeys(mentioned))
    if len(mentioned) > 1:
        return ConfirmationDecision("ambiguous", reason="multiple match ids mentioned")
    if mentioned and mentioned[0] not in live_ids:
        return ConfirmationDecision("rejected", reason="stale or unknown match id")

    core = _MATCH_ID_RE.sub(" ", text)
    core = _strip_polite_wrappers(re.sub(r"\s+", " ", core).strip())
    if core not in _APPROVAL_CORES:
        return ConfirmationDecision("not_confirmation", reason="not an explicit approval phrase")

    if mentioned:
        resolved = live_ids[mentioned[0]]
    elif len(live_ids) == 1:
        resolved = next(iter(live_ids.values()))
    else:
        return ConfirmationDecision(
            "ambiguous", reason="multiple live matches require an explicit match id"
        )

    if requested_match_id and requested_match_id.casefold() != resolved.casefold():
        return ConfirmationDecision(
            "rejected", reason="tool match id differs from the user's approval"
        )
    return ConfirmationDecision("approved", match_id=resolved)
