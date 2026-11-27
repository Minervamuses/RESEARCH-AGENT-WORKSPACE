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

test("layout.css loads after document.css and preserves original grid defaults and single-column breakpoints", async () => {
  const mainTsx = await readFile(resolve(currentDir, "../src/main.tsx"), "utf8");
  const stylesCss = await readFile(resolve(currentDir, "../src/styles.css"), "utf8");
  const documentCss = await readFile(resolve(currentDir, "../src/styles/document.css"), "utf8");
  const responsiveCss = await readFile(resolve(currentDir, "../src/styles/responsive.css"), "utf8");
  const layoutCss = await readFile(resolve(currentDir, "../src/styles/layout.css"), "utf8");

  const docImport = mainTsx.indexOf('import "./styles/document.css"');
  const layoutImport = mainTsx.indexOf('import "./styles/layout.css"');
  assert.ok(docImport >= 0 && layoutImport > docImport, "layout.css must be imported after document.css");

  assert.doesNotMatch(
    layoutCss,
    /\.(app-shell|writing-workspace)[^{]*\{[^}]*grid-template-columns/s,
    "layout.css must not redefine .app-shell or .writing-workspace grid-template-columns",
  );

  // Original default tracks stay as CSS variable fallbacks.
  assert.match(stylesCss, /var\(--sidebar-track,\s*minmax\(10\.15rem,\s*11\.9rem\)\)/);
  assert.match(documentCss, /var\(--document-fr,\s*1\.05fr\)/);
  assert.match(documentCss, /var\(--conversation-fr,\s*1fr\)/);

  // Single-column responsive breakpoints remain intact.
  assert.match(responsiveCss, /@media\s*\(max-width:\s*760px\)\s*\{[\s\S]*?\.app-shell\s*\{[^}]*grid-template-columns:\s*1fr;/);
  assert.match(documentCss, /@media\s*\(max-width:\s*1050px\)\s*\{[\s\S]*?\.writing-workspace\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/);

  // Multi-column grid-column placement is scoped to desktop widths only.
  const desktopShellMedia = stylesCss.match(/@media\s*\(min-width:\s*761px\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  assert.match(desktopShellMedia, /\.app-shell\s*>\s*\.sidebar\s*\{[^}]*grid-column:/);
  assert.match(desktopShellMedia, /\.app-shell\s*>\s*\.main-workspace\s*\{[^}]*grid-column:/);

  const desktopWorkspaceMedia = documentCss.match(/@media\s*\(min-width:\s*1051px\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  assert.match(desktopWorkspaceMedia, /\.writing-workspace\s*>\s*\.document-pane\s*\{[^}]*grid-column:\s*1;/);
  assert.match(desktopWorkspaceMedia, /\.writing-workspace\s*>\s*\.column-resizer-workspace\s*\{[^}]*grid-column:\s*2;/);
  assert.match(desktopWorkspaceMedia, /\.writing-workspace\s*>\s*\.workspace-body\s*\{[^}]*grid-column:\s*3;/);
});
