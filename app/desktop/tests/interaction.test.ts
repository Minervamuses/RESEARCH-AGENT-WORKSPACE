import assert from "node:assert/strict";
import test from "node:test";

import {
  dialogKeyDecision,
  focusLeftContainer,
  menuNextIndex,
  menuShouldClose,
  type DialogKeyPolicy,
} from "../src/lib/interaction.ts";

const policy: DialogKeyPolicy = { dismissible: true, trapTab: true, blockEmptyTab: false, preventEscapeWhenBlocked: false };

test("Tab wraps from the last control to the first and Shift+Tab from the first to the last", () => {
  assert.deepEqual(dialogKeyDecision("Tab", false, 2, 3, policy), { preventDefault: true, dismiss: false, focus: "first" });
  assert.deepEqual(dialogKeyDecision("Tab", true, 0, 3, policy), { preventDefault: true, dismiss: false, focus: "last" });
  assert.deepEqual(dialogKeyDecision("Tab", false, 1, 3, policy), { preventDefault: false, dismiss: false, focus: null });
  assert.deepEqual(dialogKeyDecision("Tab", true, 1, 3, policy), { preventDefault: false, dismiss: false, focus: null });
  // Focus outside the enabled controls (for example on the panel itself) is left to the browser.
  assert.equal(dialogKeyDecision("Tab", false, -1, 3, policy).preventDefault, false);
  assert.equal(dialogKeyDecision("Tab", true, -1, 3, policy).preventDefault, false);
});

test("with no enabled control Tab is swallowed only where the dialog asks for it", () => {
  assert.equal(dialogKeyDecision("Tab", false, -1, 0, { ...policy, blockEmptyTab: true }).preventDefault, true);
  assert.equal(dialogKeyDecision("Tab", false, -1, 0, policy).preventDefault, false);
});

test("a non-modal dialog never traps Tab", () => {
  const nonModal = { ...policy, trapTab: false, blockEmptyTab: true };
  assert.deepEqual(dialogKeyDecision("Tab", false, 2, 3, nonModal), { preventDefault: false, dismiss: false, focus: null });
  assert.deepEqual(dialogKeyDecision("Tab", false, -1, 0, nonModal), { preventDefault: false, dismiss: false, focus: null });
});

test("Esc dismisses only while allowed; the approval policy consumes it either way", () => {
  assert.deepEqual(dialogKeyDecision("Escape", false, 0, 2, policy), { preventDefault: true, dismiss: true, focus: null });
  const busy = { ...policy, dismissible: false };
  assert.deepEqual(dialogKeyDecision("Escape", false, 0, 2, busy), { preventDefault: false, dismiss: false, focus: null });
  assert.deepEqual(dialogKeyDecision("Escape", false, 0, 2, { ...busy, preventEscapeWhenBlocked: true }),
    { preventDefault: true, dismiss: false, focus: null });
  assert.deepEqual(dialogKeyDecision("Enter", false, 0, 2, policy), { preventDefault: false, dismiss: false, focus: null });
});

test("menus close on Esc only when open; a context menu also closes on Tab", () => {
  assert.equal(menuShouldClose("Escape", true), true);
  assert.equal(menuShouldClose("Escape", false), false);
  assert.equal(menuShouldClose("Tab", true), false);
  assert.equal(menuShouldClose("Tab", true, true), true);
  assert.equal(menuShouldClose("ArrowDown", true, true), false);
});

test("menu arrows wrap, Home and End exist only where enabled, other keys pass through", () => {
  assert.equal(menuNextIndex("ArrowDown", 1, 3, false), 2);
  assert.equal(menuNextIndex("ArrowDown", 2, 3, false), 0);
  assert.equal(menuNextIndex("ArrowUp", 0, 3, false), 2);
  assert.equal(menuNextIndex("Home", 2, 3, true), 0);
  assert.equal(menuNextIndex("End", 0, 3, true), 2);
  assert.equal(menuNextIndex("Home", 2, 3, false), null);
  assert.equal(menuNextIndex("End", 0, 3, false), null);
  assert.equal(menuNextIndex("a", 0, 3, true), null);
  assert.equal(menuNextIndex("ArrowDown", -1, 3, false), 0);
  assert.equal(menuNextIndex("ArrowDown", 0, 0, false), -1);
});

test("blur closes a menu only when focus leaves its container", () => {
  const inside = {} as Node;
  const container = { contains: (node: Node | null) => node === inside };
  assert.equal(focusLeftContainer(container, inside), false);
  assert.equal(focusLeftContainer(container, {} as Node), true);
  assert.equal(focusLeftContainer(container, null), true);
});
