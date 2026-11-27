import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  createOutlineTracker,
  findActiveHeadingId,
  jumpEditorToOffset,
  MONACO_SCROLL_TYPE_IMMEDIATE,
  parseOutline,
  performOutlineClick,
  planOutlineUpdate,
  recomputeOutline,
  resolveActiveOutlineDisplay,
  toggleCollapsedId,
  type EditorOutlineHandle,
  type JumpableEditor,
  type OutlineSourceInput,
} from "../src/lib/outline/index.ts";

const SAMPLE_MD = [
  "Preamble line 1",
  "Preamble line 2",
  "# Chapter 1", // line 3
  "Body 1",
  "## Section 1.1", // line 5
  "Body 1.1",
  "### Detail 1.1.1", // line 7
  "Body 1.1.1 line A",
  "Body 1.1.1 line B",
  "# Chapter 2", // line 10
  "Body 2",
  "## Final Section", // line 12
  "Last line 13",
].join("\n");

test("findActiveHeadingId picks exact heading lines, mid-section lines, innermost nested section, and null before first heading", () => {
  const outline = parseOutline("paper.md", SAMPLE_MD);
  const [ch1, sec11, det111, ch2, finalSec] = outline.flat;

  assert.equal(findActiveHeadingId(outline.flat, 1), null);
  assert.equal(findActiveHeadingId(outline.flat, 2), null);
  assert.equal(findActiveHeadingId(outline.flat, 3), ch1.id);
  assert.equal(findActiveHeadingId(outline.flat, 4), ch1.id);
  assert.equal(findActiveHeadingId(outline.flat, 5), sec11.id);
  assert.equal(findActiveHeadingId(outline.flat, 6), sec11.id);
  assert.equal(findActiveHeadingId(outline.flat, 7), det111.id);
  assert.equal(findActiveHeadingId(outline.flat, 9), det111.id, "innermost nested heading wins");
  assert.equal(findActiveHeadingId(outline.flat, 10), ch2.id);
  assert.equal(findActiveHeadingId(outline.flat, 12), finalSec.id);
  assert.equal(findActiveHeadingId(outline.flat, 99), finalSec.id);
});

test("resolveActiveOutlineDisplay highlights nearest visible collapsed ancestor without auto-expanding", () => {
  const outline = parseOutline("paper.md", SAMPLE_MD);
  const [ch1, sec11, det111] = outline.flat;

  // Expanded: active node itself is highlighted.
  assert.deepEqual(
    resolveActiveOutlineDisplay(outline, det111.id, new Set()),
    { activeId: det111.id, activeAncestorId: null },
  );

  // Direct parent collapsed: parent gets ancestor highlight.
  assert.deepEqual(
    resolveActiveOutlineDisplay(outline, det111.id, new Set([sec11.id])),
    { activeId: null, activeAncestorId: sec11.id },
  );

  // Both root and parent collapsed: highest collapsed (actually visible) ancestor gets highlight.
  assert.deepEqual(
    resolveActiveOutlineDisplay(outline, det111.id, new Set([ch1.id, sec11.id])),
    { activeId: null, activeAncestorId: ch1.id },
  );

  // Active node itself collapsed: it is still visible, so direct active highlight applies.
  assert.deepEqual(
    resolveActiveOutlineDisplay(outline, sec11.id, new Set([sec11.id])),
    { activeId: sec11.id, activeAncestorId: null },
  );
});

test("jump guard blocks synchronous and rAF-delayed programmatic events at bottom of file, and disarms on real user movement", () => {
  const outline = parseOutline("paper.md", SAMPLE_MD);
  const [ch1, , det111, , finalSec] = outline.flat;
  const tracker = createOutlineTracker(outline);

  const notifications: (string | null)[] = [];
  tracker.subscribe(() => notifications.push(tracker.getSnapshot()));

  // Replay exact sequence for synchronous programmatic scroll event (e.g. bottom of file where topLine is line 5).
  tracker.armJump(finalSec.id, finalSec.lineNumber);
  assert.equal(tracker.getSnapshot(), finalSec.id);
  tracker.reportCursorLine(finalSec.lineNumber);
  // Synchronous scroll arriving before recordJumpScrollTop (expectedScrollTop still null):
  tracker.reportViewport(5, 420);
  tracker.recordJumpScrollTop(420);
  assert.equal(tracker.getSnapshot(), finalSec.id, "synchronous jump scroll must not bounce active section back");

  // rAF-delayed scroll with the same recorded scrollTop:
  tracker.reportViewport(5, 420);
  assert.equal(tracker.getSnapshot(), finalSec.id, "rAF-delayed scroll at recorded scrollTop must stay on target");

  // Real user scroll to a different scrollTop disarms the guard and resumes normal tracking:
  tracker.reportViewport(7, 260);
  assert.equal(tracker.getSnapshot(), det111.id);

  // Moving cursor to another line after a jump also disarms the guard:
  tracker.armJump(finalSec.id, finalSec.lineNumber);
  tracker.reportCursorLine(finalSec.lineNumber);
  tracker.recordJumpScrollTop(420);
  tracker.reportCursorLine(3);
  assert.equal(tracker.getSnapshot(), ch1.id);

  // Subscribers are only notified when activeId actually changes.
  const countBefore = notifications.length;
  tracker.reportCursorLine(4); // still in ch1
  assert.equal(notifications.length, countBefore, "duplicate activeId must not notify subscribers");
});

test("tracker recomputes active section after outline re-parse and clears completely on reset", () => {
  const outline1 = parseOutline("paper.md", "# A\nline 2\nline 3\n# B\nline 5\n");
  const tracker = createOutlineTracker(outline1);

  tracker.reportCursorLine(4);
  assert.equal(tracker.getSnapshot(), outline1.flat[1].id, "line 4 is initially in B");

  // Insert two lines above # B so # B moves to line 6; saved cursor line 4 is now back inside # A.
  const outline2 = parseOutline("paper.md", "# A\nline 2\nline 3\nextra 1\nextra 2\n# B\nline 7\n");
  tracker.setOutline(outline2);
  assert.equal(tracker.getSnapshot(), outline2.flat[0].id, "re-parse recomputes active section from saved cursor line");

  // Reset drops active section, saved position and any jump guard.
  tracker.armJump(outline2.flat[1].id, outline2.flat[1].lineNumber);
  tracker.recordJumpScrollTop(100);
  tracker.reset();
  assert.equal(tracker.getSnapshot(), null);

  // After reset, installing a new outline has no saved line and no lingering jump guard.
  tracker.setOutline(outline1);
  assert.equal(tracker.getSnapshot(), null);
  tracker.reportViewport(4, 100);
  assert.equal(tracker.getSnapshot(), outline1.flat[1].id, "no stale jump guard remains after reset");
});

test("jump sequence invokes armJump -> setPosition -> revealLineNearTop(Immediate) -> focus and never touches selection or document", () => {
  const source = "# Intro\nBody\n## Methods\nDetails\n";
  const outline = parseOutline("paper.md", source);
  const methods = outline.flat[1];
  const calls: string[] = [];
  let setSelectionCalled = false;
  let rangedOnChangeCalled = false;

  const baseTracker = createOutlineTracker(outline);
  const tracker = {
    ...baseTracker,
    armJump(id: string, line: number) {
      calls.push(`armJump:${id}@${line}`);
      baseTracker.armJump(id, line);
    },
    recordJumpScrollTop(scrollTop: number) {
      calls.push(`recordJumpScrollTop:${scrollTop}`);
      baseTracker.recordJumpScrollTop(scrollTop);
    },
  };

  const fakeEditor: JumpableEditor & { setSelection?: () => void } = {
    setPosition(pos) {
      calls.push(`setPosition:${pos.lineNumber}:${pos.column}`);
    },
    revealLineNearTop(line, scrollType) {
      calls.push(`revealLineNearTop:${line}:${scrollType}`);
    },
    focus() {
      calls.push("focus");
    },
    getScrollTop() {
      calls.push("getScrollTop");
      return 312;
    },
    setSelection() {
      setSelectionCalled = true;
    },
  };
  const onChange = (range?: { start: number; end: number }) => {
    if (range) rangedOnChangeCalled = true;
  };
  void onChange;

  const handle: EditorOutlineHandle = {
    jumpToOffset: (offset) => jumpEditorToOffset(fakeEditor, source, offset, MONACO_SCROLL_TYPE_IMMEDIATE),
  };

  const outcome = performOutlineClick({
    clickedNode: methods,
    outline,
    currentSourceText: source,
    refreshOutline: () => outline,
    tracker,
    handle,
  });

  assert.equal(outcome, "jumped");
  assert.deepEqual(calls, [
    `armJump:${methods.id}@3`,
    "setPosition:3:1",
    `revealLineNearTop:3:${MONACO_SCROLL_TYPE_IMMEDIATE}`,
    "focus",
    "getScrollTop",
    "recordJumpScrollTop:312",
  ]);
  assert.equal(setSelectionCalled, false);
  assert.equal(rangedOnChangeCalled, false);
});

test("stale outline clicks jump only when chain is unambiguous in both old and new trees, and null handles are ignored safely", () => {
  // 1. Unique heading shifted down by an unrelated paragraph -> refreshes and jumps to new offset.
  const oldText1 = "# Intro\n## Methods\n";
  const newText1 = "# Intro\nNew line 1\nNew line 2\n## Methods\n";
  const oldOutline1 = parseOutline("a.md", oldText1);
  let latestOutline1 = oldOutline1;
  const tracker1 = createOutlineTracker(oldOutline1);
  const jumpedOffsets1: number[] = [];
  const handle1: EditorOutlineHandle = {
    jumpToOffset: (offset) => {
      jumpedOffsets1.push(offset);
      return 40;
    },
  };
  const res1 = performOutlineClick({
    clickedNode: oldOutline1.flat[1],
    outline: oldOutline1,
    currentSourceText: newText1,
    refreshOutline: () => {
      latestOutline1 = parseOutline("a.md", newText1);
      return latestOutline1;
    },
    tracker: tracker1,
    handle: handle1,
  });
  assert.equal(res1, "jumped");
  assert.deepEqual(jumpedOffsets1, [latestOutline1.flat[1].startOffsetUtf16]);
  assert.notEqual(latestOutline1.flat[1].startOffsetUtf16, oldOutline1.flat[1].startOffsetUtf16);

  // 2. Duplicate siblings: deleting first `## Results` and clicking old item 1 refreshes only, no jump;
  //    subsequent click on refreshed outline jumps normally.
  const oldText2 = "# Study\n## Results\nA\n## Results\nB\n";
  const newText2 = "# Study\n## Results\nB\n";
  const oldOutline2 = parseOutline("b.md", oldText2);
  let latestOutline2 = oldOutline2;
  const tracker2 = createOutlineTracker(oldOutline2);
  const jumpedOffsets2: number[] = [];
  const handle2: EditorOutlineHandle = {
    jumpToOffset: (offset) => {
      jumpedOffsets2.push(offset);
      return 10;
    },
  };
  const res2 = performOutlineClick({
    clickedNode: oldOutline2.flat[1], // first Results (ambiguous in old tree)
    outline: oldOutline2,
    currentSourceText: newText2,
    refreshOutline: () => {
      latestOutline2 = parseOutline("b.md", newText2);
      return latestOutline2;
    },
    tracker: tracker2,
    handle: handle2,
  });
  assert.equal(res2, "refreshed");
  assert.deepEqual(jumpedOffsets2, [], "ambiguous stale duplicate must not jump");

  const res2Retry = performOutlineClick({
    clickedNode: latestOutline2.flat[1],
    outline: latestOutline2,
    currentSourceText: newText2,
    refreshOutline: () => latestOutline2,
    tracker: tracker2,
    handle: handle2,
  });
  assert.equal(res2Retry, "jumped");
  assert.deepEqual(jumpedOffsets2, [latestOutline2.flat[1].startOffsetUtf16]);

  // 3. Duplicate ancestor ambiguity -> refresh only, no jump.
  const oldText3 = "# Study\n## Unique\n# Study\n## Other\n";
  const newText3 = "Inserted\n# Study\n## Unique\n# Study\n## Other\n";
  const oldOutline3 = parseOutline("c.md", oldText3);
  const jumpedOffsets3: number[] = [];
  const res3 = performOutlineClick({
    clickedNode: oldOutline3.flat[1], // Unique under duplicate # Study
    outline: oldOutline3,
    currentSourceText: newText3,
    refreshOutline: () => parseOutline("c.md", newText3),
    tracker: createOutlineTracker(oldOutline3),
    handle: { jumpToOffset: (o) => { jumpedOffsets3.push(o); return 0; } },
  });
  assert.equal(res3, "refreshed");
  assert.deepEqual(jumpedOffsets3, []);

  // 4. Target heading deleted -> refresh only, no jump.
  const oldOutline4 = parseOutline("d.md", "# A\n# Deleted\n");
  const jumpedOffsets4: number[] = [];
  const res4 = performOutlineClick({
    clickedNode: oldOutline4.flat[1],
    outline: oldOutline4,
    currentSourceText: "# A\n",
    refreshOutline: () => parseOutline("d.md", "# A\n"),
    tracker: createOutlineTracker(oldOutline4),
    handle: { jumpToOffset: (o) => { jumpedOffsets4.push(o); return 0; } },
  });
  assert.equal(res4, "refreshed");
  assert.deepEqual(jumpedOffsets4, []);

  // 5. Null handle (editor still loading or switching) -> silently ignored, active section unchanged.
  const tracker5 = createOutlineTracker(oldOutline1);
  tracker5.reportCursorLine(1);
  const before5 = tracker5.getSnapshot();
  assert.doesNotThrow(() => {
    const res5 = performOutlineClick({
      clickedNode: oldOutline1.flat[1],
      outline: oldOutline1,
      currentSourceText: oldText1,
      refreshOutline: () => oldOutline1,
      tracker: tracker5,
      handle: null,
    });
    assert.equal(res5, "ignored");
  });
  assert.equal(tracker5.getSnapshot(), before5);
});

test("DocumentEditor keeps model creation scoped to [value?.rootPath, value?.path] and disposes outline listeners", () => {
  const source = readFileSync(new URL("../src/DocumentEditor.tsx", import.meta.url), "utf8");
  assert.match(source, /\}, \[value\?\.rootPath, value\?\.path\]\);/);
  assert.match(source, /cursorListener\.dispose\(\);/);
  assert.match(source, /scrollListener\.dispose\(\);/);
  assert.match(source, /cancelAnimationFrame\(scrollFrameId\);/);
  assert.match(source, /onHandle\?\.\(null\);/);
});

test("live update simulation covers add, delete, rename, re-level, large paste, Agent edit, Undo and file switch", () => {
  const tracker = createOutlineTracker();
  let prev: OutlineSourceInput | null = null;
  let collapsed = new Set<string>();

  const apply = (next: OutlineSourceInput | null, expectedPlan: "immediate" | "debounce" | "clear" | "noop") => {
    const plan = planOutlineUpdate(prev, next);
    assert.equal(plan, expectedPlan);
    const resetCollapse = plan === "immediate" || plan === "clear";
    if (resetCollapse) tracker.reset();
    const result = recomputeOutline(next, collapsed, resetCollapse);
    collapsed = result.collapsedIds;
    tracker.setOutline(result.outline);
    prev = next;
    return result.outline;
  };

  // 1. Open Markdown file.
  const v1Text = "# Intro\n## Scope\n# Methods\n## Data\n";
  const v1 = apply({ rootPath: "/p", path: "draft.md", sourceText: v1Text }, "immediate");
  const introId = v1.roots[0].id;
  const methodsId = v1.roots[1].id;
  collapsed = toggleCollapsedId(collapsed, introId);
  collapsed = toggleCollapsedId(collapsed, methodsId);
  tracker.reportCursorLine(3);
  assert.equal(tracker.getSnapshot(), methodsId);

  // 2. Add a new heading -> debounce; collapsed parents remain collapsed.
  const v2Text = "# Intro\n## Scope\n# Methods\n## Data\n## Analysis\n";
  const v2 = apply({ rootPath: "/p", path: "draft.md", sourceText: v2Text }, "debounce");
  assert.deepEqual(v2.roots[1].children.map((c) => c.title), ["Data", "Analysis"]);
  assert.ok(collapsed.has(introId) && collapsed.has(methodsId));

  // 3. Delete a heading (`# Intro`) -> its collapsed ID is pruned; `# Methods` stays collapsed.
  const v3Text = "# Methods\n## Data\n## Analysis\n";
  const v3 = apply({ rootPath: "/p", path: "draft.md", sourceText: v3Text }, "debounce");
  assert.ok(!collapsed.has(introId), "deleted node collapsed ID must be pruned");
  assert.ok(collapsed.has(methodsId), "surviving node collapsed ID must be kept");
  assert.equal(v3.roots.length, 1);

  // 4. Rename `## Data` -> `## Dataset`.
  const v4Text = "# Methods\n## Dataset\n## Analysis\n";
  const v4 = apply({ rootPath: "/p", path: "draft.md", sourceText: v4Text }, "debounce");
  assert.deepEqual(v4.roots[0].children.map((c) => c.title), ["Dataset", "Analysis"]);
  assert.ok(collapsed.has(methodsId));

  // 5. Re-level `## Analysis` to `### Analysis` (nests under `## Dataset`).
  const v5Text = "# Methods\n## Dataset\n### Analysis\n";
  const v5 = apply({ rootPath: "/p", path: "draft.md", sourceText: v5Text }, "debounce");
  assert.equal(v5.roots[0].children.length, 1);
  assert.equal(v5.roots[0].children[0].children[0].title, "Analysis");
  assert.equal(v5.roots[0].children[0].children[0].depth, 2);

  // 6. Paste a large multi-section block (40 headings).
  const pastedBlock = Array.from({ length: 40 }, (_, i) => `## Pasted ${i + 1}\nParagraph ${i + 1}\n`).join("");
  const v6Text = `${v5Text}\n${pastedBlock}`;
  const v6 = apply({ rootPath: "/p", path: "draft.md", sourceText: v6Text }, "debounce");
  assert.equal(v6.flat.length, 43);
  assert.ok(collapsed.has(methodsId));

  // 7. Agent modification replaces sections without saving to disk.
  const v7Text = "# Methods\n## Agent Revised Pipeline\n# Discussion\n";
  const v7 = apply({ rootPath: "/p", path: "draft.md", sourceText: v7Text }, "debounce");
  assert.deepEqual(v7.flat.map((n) => n.title), ["Methods", "Agent Revised Pipeline", "Discussion"]);
  assert.ok(collapsed.has(methodsId));

  // 8. Undo restores v1 content; tracker recomputes active section for saved cursor line 3 (`# Methods`).
  const v8 = apply({ rootPath: "/p", path: "draft.md", sourceText: v1Text }, "debounce");
  assert.deepEqual(v8.flat.map((n) => n.title), ["Intro", "Scope", "Methods", "Data"]);
  assert.equal(tracker.getSnapshot(), v8.roots[1].id);

  // 9. Switch to another file (.tex) -> immediate parse, collapse reset, tracker reset, no leftover nodes.
  const texText = "\\section{Background}\n\\subsection{Prior Work}\n";
  const v9 = apply({ rootPath: "/p", path: "paper.tex", sourceText: texText }, "immediate");
  assert.equal(v9.format, "latex");
  assert.deepEqual(v9.flat.map((n) => n.title), ["Background", "Prior Work"]);
  assert.equal(collapsed.size, 0, "file switch must clear collapsed state");
  assert.equal(tracker.getSnapshot(), null, "file switch must reset active section");
});
