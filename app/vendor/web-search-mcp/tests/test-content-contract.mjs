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

// Whole-page conversion: each source text once, in order, without glued blocks.
const parse = (source, url = 'https://final.example/redirected/page') => extractor.parseContent(source, url);
const count = (haystack, needle) => haystack.split(needle).length - 1;
const nest = depth => depth === 0 ? 'LEAF' : `<table><tr><td>L${depth}</td><td>${nest(depth - 1)}</td></tr></table>`;
for (let depth = 1; depth <= 6; depth++) {
  const nested = parse(nest(depth));
  assert.equal(count(nested, 'LEAF'), 1, `nested depth ${depth}`);
  for (let level = 1; level <= depth; level++) assert.equal(nested.match(new RegExp(`\\bL${level}\\b`, 'g'))?.length, 1);
}
const [len8, len16] = [8, 16].map(depth => parse(nest(depth)).length);
assert.ok(len16 < 2.5 * len8, `nested output grows linearly: ${len8} -> ${len16}`);
const stories = parse('<p>Intro</p><article><h2>Story 1</h2></article><article><h2>Story 2</h2></article><p>Tail</p>');
const order = ['Intro', 'Story 1', 'Story 2', 'Tail'].map(word => stories.indexOf(word));
assert.ok(order.every((at, i) => at >= 0 && (i === 0 || at > order[i - 1])), stories);
const aside = parse('<aside><article>Related</article></aside><main>Main</main>');
assert.ok(aside.includes('Related') && aside.includes('Main'), aside);
const glued = parse('<p>Lead</p><address>Addr</address><aside>Side</aside><dl><dt>Term</dt><dd>Def</dd></dl>'
  + '<details><summary>Sum</summary>Detail</details><dialog>Dlg</dialog><fieldset><legend>Leg</legend>Field</fieldset>'
  + '<footer>Foot</footer><form>Form</form><header>Head</header><hgroup>Hgr</hgroup>Left<hr>Right<menu>Menu</menu><nav>Nav</nav>'
  + '<select><optgroup label="g"><option>OptA</option><option>OptB</option></optgroup><optgroup label="h"><option>OptC</option></optgroup></select>'
  + '<search>Srch</search>End');
const tokens = glued.split(/\s+/);
for (const word of ['Lead', 'Addr', 'Side', 'Term', 'Def', 'Sum', 'Detail', 'Dlg', 'Leg', 'Field', 'Foot', 'Form', 'Head', 'Hgr',
  'Left', 'Right', 'Menu', 'Nav', 'OptA', 'OptB', 'OptC', 'Srch', 'End']) {
  assert.ok(tokens.includes(word), `glued block text around ${word}: ${JSON.stringify(glued)}`);
}
assert.doesNotMatch(glued, /TermDef/);
const captioned = parse('<table><caption>Cap text</caption><tr><td><p>One</p><p>Two</p></td><td>Three</td></tr><tr><td>Four</td></tr></table>');
assert.equal(count(captioned, 'Cap text'), 1);
assert.match(captioned, /Cap text[^]*span structure simplified\]\nOne Two \| Three\nFour/);
assert.match(parse('<base href="/docs/sub/"><a href="next">Next</a>'), /\[Next\]\(<https:\/\/final\.example\/docs\/sub\/next>\)/);
assert.match(parse('<a href="next">Next</a>'), /\[Next\]\(<https:\/\/final\.example\/redirected\/next>\)/);
assert.match(parse('<a href="/x">Line\n one   <p>two</p></a>'), /\[Line one two\]\(<https:\/\/final\.example\/x>\)/);
const titled = html => { const state = { contentType: 'text/html', status: 'not_attempted' }; extractor.convertResponse(Buffer.from(html), state); return state.pageTitle; };
assert.equal(titled('<html><head></head><body><svg><title>Icon</title></svg><p>x</p></body></html>'), undefined);
assert.equal(titled('<html><head><title>  A\n  B </title></head><body><svg><title>Icon</title></svg></body></html>'), 'A B');
process.stdout.write('whole-page conversion, tables once, block separators, base and title: passed\n');

// Every fixed candidate survives media/error/empty outcomes, in original order.
const candidates = ['pdf-without-extension', 'error', 'short', 'empty', 'cancelled'].map(id => ({
  title: id, url: `https://example.org/${id}`, description: `snippet-${id}`,
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
extractor.extractWithBrowser = async (_options, _state, started) => { started(); events.push('browser-empty'); return ''; };
const results = await extractor.extractContentForResults(candidates, 5, 7);
assert.deepEqual(results.map(r => r.url), candidates.map(r => r.url));
assert.deepEqual(results.map(r => r.read.status), ['unsupported_media', 'http_error', 'text', 'empty_text', 'cancelled']);
assert.equal(results[2].read.pageTitle, 'Own page');
assert.equal(results[2].read.content, 'OK.');
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
