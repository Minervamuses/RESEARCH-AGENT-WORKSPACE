// Runs each F1-S1 check separately against a dist directory: node discriminate.mjs <dist-dir>
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const dist = path.resolve(process.argv[2]);
const { EnhancedContentExtractor } = await import(pathToFileURL(path.join(dist, 'enhanced-content-extractor.js')).href);
const extractor = new EnhancedContentExtractor();
const parse = (source, url = 'https://final.example/redirected/page') => extractor.parseContent(source, url);
const count = (haystack, needle) => haystack.split(needle).length - 1;
const nest = depth => depth === 0 ? 'LEAF' : `<table><tr><td>L${depth}</td><td>${nest(depth - 1)}</td></tr></table>`;
const titled = html => { const state = { contentType: 'text/html', status: 'not_attempted' }; extractor.convertResponse(Buffer.from(html), state); return state.pageTitle; };
const checks = {
  nested_once_1_to_6: () => { for (let d = 1; d <= 6; d++) assert.equal(count(parse(nest(d)), 'LEAF'), 1); },
  nested_linear_16: () => { const [a, b] = [8, 16].map(d => parse(nest(d)).length); assert.ok(b < 2.5 * a, `${a}->${b}`); },
  articles_in_order: () => { const t = parse('<p>Intro</p><article><h2>Story 1</h2></article><article><h2>Story 2</h2></article><p>Tail</p>'); const o = ['Intro', 'Story 1', 'Story 2', 'Tail'].map(w => t.indexOf(w)); assert.ok(o.every((x, i) => x >= 0 && (i === 0 || x > o[i - 1]))); },
  aside_and_main: () => { const t = parse('<aside><article>Related</article></aside><main>Main</main>'); assert.ok(t.includes('Related') && t.includes('Main')); },
  no_glued_dl: () => assert.doesNotMatch(parse('<dl><dt>Term</dt><dd>Def</dd></dl>'), /TermDef/),
  no_glued_nav_footer: () => assert.doesNotMatch(parse('<nav>Nav</nav><footer>Foot</footer>'), /NavFoot/),
  caption_once_and_one_line_row: () => { const t = parse('<table><caption>Cap text</caption><tr><td><p>One</p><p>Two</p></td><td>Three</td></tr></table>'); assert.equal(count(t, 'Cap text'), 1); assert.match(t, /One Two \| Three/); },
  base_relative_to_final: () => assert.match(parse('<base href="/docs/sub/"><a href="next">Next</a>'), /<https:\/\/final\.example\/docs\/sub\/next>/),
  no_base_uses_final: () => assert.match(parse('<a href="next">Next</a>'), /<https:\/\/final\.example\/redirected\/next>/),
  link_label_single_line: () => assert.match(parse('<a href="/x">Line\n one   <p>two</p></a>'), /\[Line one two\]/),
  svg_title_not_page_title: () => assert.equal(titled('<html><head></head><body><svg><title>Icon</title></svg><p>x</p></body></html>'), undefined),
  title_whitespace: () => assert.equal(titled('<html><head><title>  A\n  B </title></head><body></body></html>'), 'A B'),
};
const out = {};
for (const [name, fn] of Object.entries(checks)) {
  try { fn(); out[name] = 'pass'; } catch (error) { out[name] = `fail: ${String(error.message).split('\n')[0].slice(0, 120)}`; }
}
process.stdout.write(JSON.stringify({ dist, checks: out }, null, 1) + '\n');
