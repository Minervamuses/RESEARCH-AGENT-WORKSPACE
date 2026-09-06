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

  const scale = rootRule.match(
    /font-size:\s*clamp\(\s*([\d.]+)rem,\s*calc\(\s*([\d.]+)rem\s*\+\s*([\d.]+)vw\s*\),\s*([\d.]+)rem\s*\)/,
  );
  assert.ok(scale, "expected a bounded viewport-responsive root font size");

  const [, minimumRem, fluidRem, fluidVw, maximumRem] = scale.map(Number);
  const browserDefault = 16;
  const fontSizeAt = (viewportWidth: number): number => Math.min(
    maximumRem * browserDefault,
    Math.max(
      minimumRem * browserDefault,
      fluidRem * browserDefault + (fluidVw / 100) * viewportWidth,
    ),
  );

  assert.equal(fontSizeAt(1080), browserDefault);
  assert.ok(fontSizeAt(1920) > fontSizeAt(1080));
  assert.equal(fontSizeAt(4000), maximumRem * browserDefault);
});
