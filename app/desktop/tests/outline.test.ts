import assert from "node:assert/strict";
import test from "node:test";
import { buildOutlineTree } from "../src/lib/outline/tree.ts";
import type { RawHeading } from "../src/lib/outline/types.ts";

function makeRaw(
  items: readonly { title: string; level: number; lineNumber: number; start: number; end?: number }[],
): RawHeading[] {
  return items.map((item) => ({
    title: item.title,
    level: item.level,
    lineNumber: item.lineNumber,
    startOffsetUtf16: item.start,
    headingEndOffsetUtf16: item.end ?? item.start + item.title.length,
  }));
}

test("tree handles discontinuous levels (H1 -> H3) and documents starting without H1", () => {
  const source = "x".repeat(200);
  const discontinuous = buildOutlineTree(
    makeRaw([
      { title: "Intro", level: 1, lineNumber: 1, start: 0, end: 7 },
      { title: "Deep", level: 3, lineNumber: 3, start: 20, end: 28 },
      { title: "Sibling", level: 2, lineNumber: 6, start: 60, end: 70 },
    ]),
    source,
    "markdown",
  );
  assert.equal(discontinuous.roots.length, 1);
  assert.equal(discontinuous.roots[0].depth, 0);
  assert.equal(discontinuous.roots[0].children.length, 2);
  assert.equal(discontinuous.roots[0].children[0].title, "Deep");
  assert.equal(discontinuous.roots[0].children[0].depth, 1);
  assert.equal(discontinuous.roots[0].children[1].title, "Sibling");
  assert.equal(discontinuous.roots[0].children[1].depth, 1);
  assert.equal(discontinuous.flat.map((n) => n.title).join(","), "Intro,Deep,Sibling");

  const noH1 = buildOutlineTree(
    makeRaw([
      { title: "First", level: 2, lineNumber: 1, start: 0, end: 8 },
      { title: "Sub", level: 3, lineNumber: 2, start: 10, end: 17 },
      { title: "Second", level: 2, lineNumber: 4, start: 40, end: 49 },
    ]),
    source,
    "markdown",
  );
  assert.equal(noH1.roots.length, 2);
  assert.equal(noH1.roots[0].depth, 0);
  assert.equal(noH1.roots[0].children[0].depth, 1);
  assert.equal(noH1.roots[1].depth, 0);
});

test("tree assigns distinct IDs to duplicate siblings and keeps IDs stable across unrelated edits", () => {
  const source = "x".repeat(300);
  const base = buildOutlineTree(
    makeRaw([
      { title: "Paper", level: 1, lineNumber: 1, start: 0 },
      { title: "Case", level: 2, lineNumber: 2, start: 20 },
      { title: "Detail", level: 3, lineNumber: 3, start: 40 },
      { title: "Case", level: 2, lineNumber: 4, start: 60 },
      { title: "Results", level: 1, lineNumber: 5, start: 100 },
    ]),
    source,
    "markdown",
  );
  const [, caseA, detail, caseB, results] = base.flat;
  assert.notEqual(caseA.id, caseB.id);
  assert.ok(detail.id.startsWith(`${caseA.id}/`));

  // Inserting an unrelated heading before does not change existing IDs.
  const inserted = buildOutlineTree(
    makeRaw([
      { title: "Preface", level: 1, lineNumber: 1, start: 0 },
      { title: "Paper", level: 1, lineNumber: 2, start: 15 },
      { title: "Case", level: 2, lineNumber: 3, start: 35 },
      { title: "Detail", level: 3, lineNumber: 4, start: 55 },
      { title: "Case", level: 2, lineNumber: 5, start: 75 },
      { title: "Results", level: 1, lineNumber: 6, start: 115 },
    ]),
    source,
    "markdown",
  );
  assert.equal(inserted.flat[1].id, base.flat[0].id);
  assert.equal(inserted.flat[2].id, caseA.id);
  assert.equal(inserted.flat[3].id, detail.id);
  assert.equal(inserted.flat[4].id, caseB.id);
  assert.equal(inserted.flat[5].id, results.id);

  // Deleting an unrelated heading before does not change remaining IDs.
  const deleted = buildOutlineTree(
    makeRaw([
      { title: "Paper", level: 1, lineNumber: 1, start: 0 },
      { title: "Results", level: 1, lineNumber: 2, start: 40 },
    ]),
    source,
    "markdown",
  );
  assert.equal(deleted.flat[1].id, results.id);

  // Renaming a unique heading changes only that node and its descendants.
  const renamed = buildOutlineTree(
    makeRaw([
      { title: "Manuscript", level: 1, lineNumber: 1, start: 0 },
      { title: "Case", level: 2, lineNumber: 2, start: 20 },
      { title: "Detail", level: 3, lineNumber: 3, start: 40 },
      { title: "Case", level: 2, lineNumber: 4, start: 60 },
      { title: "Results", level: 1, lineNumber: 5, start: 100 },
    ]),
    source,
    "markdown",
  );
  assert.notEqual(renamed.flat[0].id, base.flat[0].id);
  assert.notEqual(renamed.flat[1].id, caseA.id);
  assert.notEqual(renamed.flat[2].id, detail.id);
  assert.notEqual(renamed.flat[3].id, caseB.id);
  assert.equal(renamed.flat[4].id, results.id);

  // Deleting the first duplicate sibling re-indexes the second to the first's occurrence.
  const dropFirstCase = buildOutlineTree(
    makeRaw([
      { title: "Paper", level: 1, lineNumber: 1, start: 0 },
      { title: "Case", level: 2, lineNumber: 4, start: 60 },
      { title: "Results", level: 1, lineNumber: 5, start: 100 },
    ]),
    source,
    "markdown",
  );
  assert.equal(dropFirstCase.flat[1].id, caseA.id);
});

test("sectionEndOffsetUtf16 ends before the next same-or-higher-level heading or at EOF", () => {
  const source = "x".repeat(250);
  const doc = buildOutlineTree(
    makeRaw([
      { title: "A", level: 1, lineNumber: 1, start: 0, end: 3 },
      { title: "A1", level: 2, lineNumber: 2, start: 20, end: 25 },
      { title: "A1a", level: 3, lineNumber: 3, start: 40, end: 47 },
      { title: "A2", level: 2, lineNumber: 4, start: 80, end: 85 },
      { title: "B", level: 1, lineNumber: 5, start: 150, end: 153 },
      { title: "B1", level: 2, lineNumber: 6, start: 180, end: 185 },
    ]),
    source,
    "markdown",
  );
  const [a, a1, a1a, a2, b, b1] = doc.flat;
  assert.equal(a.sectionEndOffsetUtf16, 150);
  assert.equal(a1.sectionEndOffsetUtf16, 80);
  assert.equal(a1a.sectionEndOffsetUtf16, 80);
  assert.equal(a2.sectionEndOffsetUtf16, 150);
  assert.equal(b.sectionEndOffsetUtf16, 250);
  assert.equal(b1.sectionEndOffsetUtf16, 250);
});
