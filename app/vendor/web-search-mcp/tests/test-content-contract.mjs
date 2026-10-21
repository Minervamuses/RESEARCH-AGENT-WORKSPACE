// Inline HTML contract checks; no network or new test framework.
import assert from 'node:assert/strict';
import { EnhancedContentExtractor } from '../dist/enhanced-content-extractor.js';
import { truncateMarkdown, resolveContentLimit } from '../dist/utils.js';

const extractor = new EnhancedContentExtractor();
const html = `<html><head><title>Own intermediary title</title><base href="/docs/"></head>
<body><main><h1>中文😀 robotics captcha photographs privacy legal</h1>
<p class="shadow" id="metadata">First paragraph.</p><p>Second paragraph.</p>
<ul><li>alpha</li><li>beta</li></ul><pre>if (x) {\n  print("😀");\n}</pre>
<table><tr><th>A</th><th>B</th></tr><tr><td colspan="2">merged</td></tr></table>
<figure><img alt="source photograph"><figcaption>Actual caption</figcaption></figure>
<p><a href="../next?q=%252F&amp;x=1">Observed destination</a>
<a href="mailto:person@example.org">Email</a></p><math>x + y</math>
</main><script>never included</script></body></html>`;
const text = extractor.parseContent(html, 'https://example.org/redirected/page');
for (const word of ['中文😀', 'robotics', 'captcha', 'photographs', 'privacy', 'legal', 'First paragraph.', 'Second paragraph.', 'Actual caption', 'x + y']) {
  assert.ok(text.includes(word), `source text lost: ${word}`);
}
assert.match(text, /# 中文😀/);
assert.match(text, /First paragraph\.\n\nSecond paragraph\./);
assert.match(text, /- alpha\n\n- beta/);
assert.match(text, /  print\("😀"\)/);
assert.match(text, /A \| B/);
assert.match(text, /span structure simplified/);
assert.match(text, /Image alt text: source photograph/);
assert.match(text, /\[Observed destination\]\(<https:\/\/example.org\/next\?q=%252F&x=1>\)/);
assert.match(text, /non-navigable href: mailto:/);
assert.doesNotMatch(text, /never included/);
assert.equal(extractor.parseContent('<main><p>Short robot.</p></main>', 'https://example.org'), 'Short robot.');
const tiny = truncateMarkdown('😀中文 [link](<https://example.org/target?q=%252F>) tail', 15);
assert.equal(tiny.content, '😀中文 ');
assert.equal(tiny.returnedLength, 4);
assert.equal(tiny.truncated, true);
assert.equal(truncateMarkdown('😀中文abc', 4).content, '😀中文a');
assert.equal(Array.from(truncateMarkdown('😀'.repeat(10001), 10000).content).length, 10000);
assert.equal(resolveContentLimit(0), resolveContentLimit());
process.stdout.write('content conversion and Unicode/link truncation: passed\n');
