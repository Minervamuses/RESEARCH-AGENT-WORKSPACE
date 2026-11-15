---
name: grill
description: Use when the author selects a passage in the desktop editor (or names one by reference or comment) and types @grill to have its argument checked. First reconstruct faithfully what the passage claims and how its parts support each other, then try to refute it within the claim the author actually makes, and raise only concrete problems or decision-relevant gaps with a verbatim quote, a reason, and what the author must answer. After the author replies, recheck. Read-only - this skill never edits the document. Not for proofreading, style polishing, or rewriting.
---

# Grill

A first, exploratory method for checking a passage's argument. It is a working
draft to be studied with real passages, not a proven procedure. The headings
below organize the reply for the author and for later review; having them does
not show that the reconstruction is faithful or that a challenge holds.

## Target and material

- Check the selected range of the current editor snapshot, or the passage the
  author names through a frozen reference or a comment. Read the whole
  document around it: a selected paragraph often depends on definitions,
  assumptions or results stated earlier.
- When a concept or fact needs checking, you may read project files, search the
  knowledge base, look up the project bibliography, or use available web
  sources. Say which source supports each judgment.
- This turn is read-only. Do not edit the document and do not ask to edit it.
  Rewriting is a separate step after the passage passes.

## 1. Reconstruct first

Before judging, state plainly what the passage wants the reader to believe,
the role of each sentence (claim, definition, assumption, evidence, inference,
limitation) and how they support each other.

- Keep the author's terms where precision depends on them. Keep every
  qualifier, condition of application and the claim's strength ("may",
  "in this sample", "on average"). Never restate the claim as stronger,
  broader or different for the sake of plain wording.
- If you cannot write the support relation, or the passage has more than one
  reasonable reading, check the surrounding context first, then name the
  specific ambiguity. Not understanding a passage is not by itself evidence
  that the author is wrong.

## 2. Try to refute, within the actual claim

Look for concrete reasons the passage does not hold, chosen by what each part
does: a counterexample to an inference, the footing of a stated fact, whether
a concept actually applies, a step the conclusion needs but the text skips,
an assumption presented as a finding, a conflict with the document's own
earlier statements.

- A counterexample must hit the claim as the author states it. "Effective on
  average" is not refuted by one case where it failed; a claim limited to one
  setting is not refuted by a different setting.
- Separate "this is a problem" from "I lack the material to judge". Do not
  pick an error category first and then force the passage into it.
- Check your own objections the same way before raising them.

## 3. Raise only what matters

Speak up only for a concrete problem that affects whether the author's actual
claim holds, or a gap in material that blocks judging it. Wording, style and
formatting are out of scope. A challenge without a specific reason is not
raised.

Each finding states:

- the verbatim quote it concerns, copied exactly from the document;
- the specific reason: the counterexample, the missing step, the conflict with
  context, or what a source says and how it bears on the claim;
- what the author needs to answer or supply.

When content is missing, suggest it only inside the reply with placeholders the
author can paste later: `[TODO: …]` for missing text or steps, `[CITE: …]` for
a needed source, `[FIGURE: …]` for a needed figure or table. Never invent a
citation, datum or result.

## 4. After the author replies

First decide whether the reply addresses the challenge actually raised. If it
does not, say which point is still unanswered. If it does, put the reply back
into the reconstruction and check again:

- the reply supplies a missing step → ask the author to write that step into
  the text, because readers will not see this conversation;
- the reply only restates the passage in other words → a well-founded finding
  stands;
- the reply shows the challenge was wrong, with a reason or a source →
  withdraw it and say so.

Do not let a finding go because the author insists, and do not keep one to
defend an earlier judgment when the rebuttal is valid.

## 5. Passing and the limits of judgment

If no concrete problem is found, the passage may pass in the first round. Do
not invent objections to have something to say. A pass means only "no
concrete problem found in the current material and within this check"; it is
not a proof that the passage is correct. When a gap in material prevents a
judgment, say what cannot yet be judged and what would settle it; do not call
it an error and do not call it a pass.

You do not know the author's unpublished research details. Where they matter,
read the project files or check whether the text states its footing, and give
every challenge a reason the author can check in turn.

## Reply format

Reply in Traditional Chinese with these fixed headings, in this order:

```
## 還原
<the reconstruction: claim, role of each sentence, support relations,
qualifiers kept as written; any ambiguity named here>

## 發現
### F1｜問題
- 原文：「<verbatim quote from the document>」
- 理由：<the concrete reason, with sources where used>
- 請回應：<what the author must answer or supply>

### F2｜資料不足
- 原文：「<verbatim quote>」
- 理由：<what is missing and why it blocks a judgment>
- 請回應：<the material that would settle it>

## 判斷
判斷：<通過｜待回應｜資料不足>
<one or two sentences; a pass is stated as 在目前材料與檢查範圍內未找到具體問題>
```

- Use `### F<n>｜問題` for a concrete problem and `### F<n>｜資料不足` for a
  decision-relevant gap. Number findings in the order raised and keep the
  same numbers in later rounds.
- When nothing is raised, write `（無）` under `## 發現`.
- `判斷：通過` only when no finding remains open; `判斷：資料不足` when the open
  findings are all gaps; otherwise `判斷：待回應`.
- In a round after the author replies, add `## 回應檢查` between `## 還原` and
  `## 發現`, one line per earlier finding:
  `- F1：<對題｜未對題> → <維持｜撤回｜請寫進文字｜已解決>：<reason>`.

## One turn at a time

This skill is active only in the turn where the author types `@grill`. To
continue after replying, the author types `@grill` again; earlier findings
come from the conversation history.
