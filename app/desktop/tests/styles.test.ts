import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const currentDir = dirname(fileURLToPath(import.meta.url));

test("desktop type scale grows on wide windows and stays bounded", async () => {
  const styles = await readFile(resolve(currentDir, "../src/styles.css"), "utf8");
  const rootRule = styles.match(/:root\s*\{(?<declarations>[\s\S]*?)\}/)?.groups?.declarations;
  assert.ok(rootRule, "expected a :root style rule");

  // calc() is optional inside clamp(), so accept either spelling of the fluid term.
  const scale = rootRule.match(
    /font-size:\s*clamp\(\s*([\d.]+)rem\s*,\s*calc\(\s*([\d.]+)rem\s*\+\s*([\d.]+)vw\s*\)\s*,\s*([\d.]+)rem\s*\)/,
  ) ?? rootRule.match(
    /font-size:\s*clamp\(\s*([\d.]+)rem\s*,\s*([\d.]+)rem\s*\+\s*([\d.]+)vw\s*,\s*([\d.]+)rem\s*\)/,
  );
  assert.ok(scale, "expected a bounded viewport-responsive root font size");

  const [, minimumRem, fluidRem, fluidVw, maximumRem] = scale.map(Number);
  assert.equal(minimumRem, 1, "narrow windows must keep the browser default size");
  assert.ok(minimumRem < maximumRem, "the scale must have room to grow");
  assert.ok(fluidRem < minimumRem, "the fluid term must start below the floor");

  // Width at which the fluid term overtakes the floor: below it the scale is
  // pinned to the browser default, above it the window earns larger text.
  const crossoverPx = ((minimumRem - fluidRem) * 16 * 100) / fluidVw;
  assert.ok(crossoverPx > 1080, "narrow windows must keep the browser default size");
  assert.ok(crossoverPx < 1920, "wide windows must actually scale up");
  const saturationPx = ((maximumRem - fluidRem) * 16 * 100) / fluidVw;
  assert.ok(saturationPx <= 4000, "very wide windows must reach the upper bound");
});
