import assert from "node:assert/strict";
import test from "node:test";
import {
  handleOutlineTreeKey,
  parseOutline,
  resolveRovingFocusId,
  visibleOutlineNodes,
} from "../src/lib/outline/index.ts";

const TREE_MD = [
  "# Chapter 1",
  "## Section 1.1",
  "### Leaf 1.1.1",
  "## Section 1.2",
  "# Chapter 2",
].join("\n");

test("outline keyboard navigation handles Up/Down/Home/End/Left/Right/Enter across expanded, collapsed, leaf and boundary nodes", () => {
  const outline = parseOutline("thesis.md", TREE_MD);
  const [ch1, sec11, leaf111, sec12, ch2] = outline.flat;

  const allVisible = visibleOutlineNodes(outline.roots, new Set());
  assert.deepEqual(allVisible.map((n) => n.id), [ch1.id, sec11.id, leaf111.id, sec12.id, ch2.id]);

  // Boundary: ArrowUp at first node stays at first; ArrowDown at last stays at last.
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), ch1.id, { key: "ArrowUp" }), {
    handled: true, nextFocusId: ch1.id, collapseChange: null, activateNode: null,
  });
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), ch2.id, { key: "ArrowDown" }), {
    handled: true, nextFocusId: ch2.id, collapseChange: null, activateNode: null,
  });

  // ArrowDown / ArrowUp move across visible rows; Home / End jump to ends.
  assert.equal(handleOutlineTreeKey(allVisible, new Set(), ch1.id, { key: "ArrowDown" }).nextFocusId, sec11.id);
  assert.equal(handleOutlineTreeKey(allVisible, new Set(), sec11.id, { key: "ArrowUp" }).nextFocusId, ch1.id);
  assert.equal(handleOutlineTreeKey(allVisible, new Set(), leaf111.id, { key: "Home" }).nextFocusId, ch1.id);
  assert.equal(handleOutlineTreeKey(allVisible, new Set(), ch1.id, { key: "End" }).nextFocusId, ch2.id);

  // ArrowRight on expanded parent moves to its first child; on leaf stays put; on collapsed expands.
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), sec11.id, { key: "ArrowRight" }), {
    handled: true, nextFocusId: leaf111.id, collapseChange: null, activateNode: null,
  });
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), leaf111.id, { key: "ArrowRight" }), {
    handled: true, nextFocusId: leaf111.id, collapseChange: null, activateNode: null,
  });
  const collapsedSec11 = new Set([sec11.id]);
  const visCollapsed = visibleOutlineNodes(outline.roots, collapsedSec11);
  assert.deepEqual(visCollapsed.map((n) => n.id), [ch1.id, sec11.id, sec12.id, ch2.id]);
  assert.deepEqual(handleOutlineTreeKey(visCollapsed, collapsedSec11, sec11.id, { key: "ArrowRight" }), {
    handled: true, nextFocusId: sec11.id, collapseChange: { id: sec11.id, collapsed: false }, activateNode: null,
  });

  // ArrowLeft on expanded parent collapses; on collapsed child or leaf moves to parent; on root leaf stays put.
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), sec11.id, { key: "ArrowLeft" }), {
    handled: true, nextFocusId: sec11.id, collapseChange: { id: sec11.id, collapsed: true }, activateNode: null,
  });
  assert.deepEqual(handleOutlineTreeKey(visCollapsed, collapsedSec11, sec11.id, { key: "ArrowLeft" }), {
    handled: true, nextFocusId: ch1.id, collapseChange: null, activateNode: null,
  });
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), leaf111.id, { key: "ArrowLeft" }), {
    handled: true, nextFocusId: sec11.id, collapseChange: null, activateNode: null,
  });
  assert.deepEqual(handleOutlineTreeKey(allVisible, new Set(), ch2.id, { key: "ArrowLeft" }), {
    handled: true, nextFocusId: ch2.id, collapseChange: null, activateNode: null,
  });

  // Enter activates the focused heading for jumping.
  const entered = handleOutlineTreeKey(allVisible, new Set(), sec12.id, { key: "Enter" });
  assert.equal(entered.handled, true);
  assert.equal(entered.activateNode?.id, sec12.id);

  // Roving tabindex resolution picks focused -> preferred active -> first visible.
  assert.equal(resolveRovingFocusId(visCollapsed, leaf111.id, sec12.id), sec12.id);
  assert.equal(resolveRovingFocusId(visCollapsed, leaf111.id, null), ch1.id);
  assert.equal(resolveRovingFocusId([], null, null), null);
});

test("outline keyboard navigation ignores IME composition, modifier shortcuts and unrelated keys", () => {
  const outline = parseOutline("thesis.md", TREE_MD);
  const visible = visibleOutlineNodes(outline.roots, new Set());
  const firstId = visible[0].id;

  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "Enter", isComposing: true }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "ArrowDown", keyCode: 229 }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "ArrowDown", ctrlKey: true }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "ArrowRight", altKey: true }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "Tab" }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "Escape" }).handled, false);
  assert.equal(handleOutlineTreeKey(visible, new Set(), firstId, { key: "a" }).handled, false);
});
