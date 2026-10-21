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

// Every fixed candidate survives media/error/empty outcomes, in original order.
const candidates = ['pdf-without-extension', 'error', 'short', 'empty', 'cancelled'].map(id => ({
  title: id, url: `https://example.org/${id}`, description: `snippet-${id}`,
  fullContent: '', contentPreview: '', wordCount: 0, timestamp: 'fixed', fetchStatus: 'not_requested',
}));
const events = [];
extractor.extractWithAxios = async (options, state) => {
  const id = new URL(options.url).pathname.slice(1);
  events.push(id);
  state.httpStatus = 200;
  state.finalUrl = options.url + '?final=1';
  state.contentType = id === 'pdf-without-extension' ? 'application/pdf' : 'text/html';
  if (id === 'error') throw Object.assign(new Error('HTTP 404'), { response: { status: 404 } });
  if (id === 'cancelled') throw Object.assign(new Error('aborted'), { code: 'ERR_CANCELED' });
  return extractor.convertResponse(Buffer.from(id === 'pdf-without-extension' ? '%PDF-1.7' : id === 'empty' ? '<html></html>' : '<title>Own page</title><p>OK.</p>'), state);
};
extractor.extractWithBrowser = async () => { events.push('browser-empty'); return ''; };
const results = await extractor.extractContentForResults(candidates, 5, 7);
assert.deepEqual(results.map(r => r.url), candidates.map(r => r.url));
assert.deepEqual(results.map(r => r.fetchStatus), ['unsupported_media', 'http_error', 'text', 'empty_text', 'cancelled']);
assert.equal(results[2].read.pageTitle, 'Own page');
assert.equal(results[2].fullContent, 'OK.');
assert.ok(results.every(r => r.description.startsWith('snippet-')));
assert.equal(results.reduce((n, r) => n + r.read.attempts.length, 0), events.length);
const unknown = { contentType: undefined, status: 'not_attempted' };
assert.equal(extractor.convertResponse(Buffer.from('<p>Cannot assume HTML</p>'), unknown), '');
assert.equal(unknown.status, 'unsupported_media');
const wrong = { contentType: 'text/html', status: 'not_attempted' };
extractor.convertResponse(Buffer.from('%PDF-1.7'), wrong);
assert.equal(wrong.status, 'unsupported_media');
process.stdout.write('candidate retention, media and actual attempts: passed\n');

const { formatSearchResponse, formatPageRead } = await import('../dist/utils.js');
const withContent = formatSearchResponse('same query', results, [], true);
assert.match(withContent, /selected=5; candidates_attempted=5; source_read_attempts=6; http_attempts=5; browser_attempts=1; transport_retries=0; returned=5/);
assert.match(withContent, /unsupported_media/);
const before = events.length;
const withoutContent = formatSearchResponse('same query', candidates, [], false);
assert.equal(events.length, before);
assert.match(withoutContent, /source_read_attempts=0/);
const urls = value => [...value.matchAll(/^URL: (.+)$/gm)].map(match => match[1]);
assert.deepEqual(urls(withContent), urls(withoutContent));
const limited = { ...results[2].read, ...truncateMarkdown('😀中文 [link](<https://example.org/path>) tail', 12) };
const pageText = formatPageRead(limited);
assert.match(pageText, /Content truncated:/);
assert.match(pageText, /remainder not delivered/);
assert.ok(pageText.includes(limited.content));
assert.equal(limited.returnedLength, Array.from(limited.content).length);
assert.equal(formatSearchResponse('x', [{ ...results[2], read: limited }], [], true).includes(pageText), true);
process.stdout.write('visible statistics, fixed candidates and transparent truncation: passed\n');
