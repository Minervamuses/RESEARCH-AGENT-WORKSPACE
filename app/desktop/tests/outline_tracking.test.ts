import assert from "node:assert/strict";
import test from "node:test";
import {
  createOutlineTracker,
  findActiveHeadingId,
  parseOutline,
  resolveActiveOutlineDisplay,
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
