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
assert.equal(truncateMarkdown('😀中文abc', 4).originalLength, 6);
assert.equal(truncateMarkdown('😀中文abc', 4).returnedLength, 4);
// At every cut a link or URL is delivered whole or not at all; no strict prefix, no dangling opening.
for (const [before, link, after] of [
  ['Intro ', '[[1]](<https://example.org/a>)', ' tail'],
  ['Intro ', '[line one\nline two](<https://example.org/b>)', ' tail'],
  ['See ', 'https://en.wikipedia.org/wiki/Foo_(bar)_baz', ' now'],
  ['Go ', '[x](https://example.org/c)', ' end'],
]) {
  const source = before + link + after;
  for (let limit = 0; limit <= source.length; limit++) {
    const { content } = truncateMarkdown(source, limit);
    assert.ok(source.startsWith(content));
    assert.ok(content.length <= before.length || content.length >= before.length + link.length,
      `limit ${limit} clipped ${JSON.stringify(link)}: ${JSON.stringify(content)}`);
  }
}
const timed = fn => { const begin = performance.now(); fn(); return performance.now() - begin; };
const brackets = '['.repeat(150 * 1024) + ' tail';
assert.ok(timed(() => truncateMarkdown(brackets, 10000)) < 1000, 'truncation of unclosed brackets is linear');
assert.equal(truncateMarkdown(brackets, 10000).returnedLength, 10000);
const spaces = `<pre>${' '.repeat(150 * 1024)}x</pre>`;
assert.ok(timed(() => extractor.parseContent(spaces, 'https://example.org')) < 1000, 'line-end trimming is linear');
assert.match(extractor.parseContent('<pre>a   \nb\t\t\nc</pre>', 'https://example.org'), /```\na\nb\nc\n```/);
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

// Declared charsets, read-limit facts, browser downloads and conversion failures (local server only).
{
  const { createServer } = await import('node:http');
  const { formatPageRead, sanitizeErrorMessage } = await import('../dist/utils.js');
  const bytes = (...parts) => Buffer.concat(parts.map(part => typeof part === 'string' ? Buffer.from(part, 'latin1') : Buffer.from(part)));
  const big = 11 * 1024 * 1024;
  const routes = {
    '/big5': ['text/html; charset=big5', bytes('<p>', [0xa4, 0xa4, 0xa4, 0xe5], '</p>')],
    '/sjis': ['text/html', bytes('<meta charset="shift_jis"><p>', [0x93, 0xfa, 0x96, 0x7b], '</p>')],
    '/cp1252': ['text/html', bytes('<meta http-equiv="Content-Type" content="text/html; charset=windows-1252"><p>caf', [0xe9], '</p>')],
    '/bom': ['text/html; charset=iso-8859-1', bytes([0xef, 0xbb, 0xbf, 0xe4, 0xb8, 0xad, 0xe6, 0x96, 0x87])],
    '/unknown': ['text/plain; charset=x-no-such-charset', bytes('plain text')],
    '/big.pdf': ['application/pdf', Buffer.concat([Buffer.from('%PDF-1.7\n'), Buffer.alloc(big)])],
    '/big.html': ['text/html', Buffer.alloc(big, 0x61)],
    '/page': ['text/html', bytes('<p>convert me</p>')],
  };
  const server = createServer((request, response) => {
    const [type, body] = routes[request.url];
    response.writeHead(200, { 'content-type': type });
    response.end(body);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const reader = new EnhancedContentExtractor();
  reader.extractWithBrowser = async () => { throw new Error('browser fallback not expected'); };
  const read = async route => reader.extractContent({ url: `${base}${route}` });
  try {
    for (const [route, text, line] of [
      ['/big5', '中文', 'Character encoding: big5 (Content-Type charset)'],
      ['/sjis', '日本', 'Character encoding: shift_jis (meta charset)'],
      ['/cp1252', 'café', 'Character encoding: windows-1252 (meta charset)'],
      ['/bom', '中文', 'Character encoding: utf-8 (BOM)'],
    ]) {
      const result = await read(route);
      assert.equal(result.status, 'text', route);
      assert.equal(result.content, text, route);
      assert.ok(formatPageRead(result).includes(line), `${route}: ${formatPageRead(result)}`);
    }
    const unknownCharset = await read('/unknown');
    assert.equal(unknownCharset.content, 'plain text');
    assert.ok(formatPageRead(unknownCharset).includes('Character encoding: utf-8 (default; unsupported charset label "x-no-such-charset"; decoded as UTF-8)'));
    const pdf = await read('/big.pdf');
    assert.deepEqual([pdf.status, pdf.httpStatus, pdf.contentType], ['unsupported_media', 200, 'application/pdf']);
    assert.match(pdf.error, /Unsupported media: application\/pdf \(response body exceeds 10 MiB read limit\)/);
    const html = await read('/big.html');
    assert.deepEqual([html.status, html.httpStatus, html.contentType], ['http_error', 200, 'text/html']);
    assert.equal(html.error, 'response body exceeds 10 MiB read limit');
    assert.match(formatPageRead(html), /HTTP status: 200; Content-Type: text\/html/);
    const failing = new EnhancedContentExtractor();
    failing.parseContent = () => { throw new Error('parse boom'); };
    failing.extractWithBrowser = async () => { throw new Error('browser fallback not expected'); };
    const httpConversion = await failing.extractContent({ url: `${base}/page` });
    assert.deepEqual([httpConversion.status, httpConversion.error, httpConversion.attempts.length], ['conversion_error', 'parse boom', 1]);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
  const ansi = '\x1b[31mpage.goto: net::ERR_ABORTED at https://example.org/file\x1b[39m\nCall log:\n  - navigating to "https://example.org/file"';
  assert.equal(sanitizeErrorMessage(new Error(ansi)), 'page.goto: net::ERR_ABORTED at https://example.org/file');

  // Browser fallback: a navigation that becomes a download is unsupported media, not an HTTP error.
  const mainFrame = {};
  const browserPage = ({ response, download, failing: fails, html: pageHtml }) => {
    const listeners = {};
    return {
      on: (event, listener) => { (listeners[event] ??= []).push(listener); },
      off: () => undefined,
      mainFrame: () => mainFrame,
      goto: async () => {
        for (const listener of response ? listeners.response ?? [] : []) {
          listener({ request: () => ({ isNavigationRequest: () => true }), frame: () => mainFrame, url: () => 'https://example.org/file.pdf', status: () => 200, headers: () => ({ 'content-type': response }) });
        }
        for (const listener of download ? listeners.download ?? [] : []) listener({ cancel: async () => undefined });
        if (fails) throw new Error(ansi);
        return { status: () => 200, headers: () => ({ 'content-type': 'text/html' }) };
      },
      url: () => 'https://example.org/file',
      evaluate: async () => 'text', waitForLoadState: async () => undefined, title: async () => '',
      content: async () => pageHtml ?? '<p>x</p>',
    };
  };
  const viaBrowser = async (page, parseFails = false) => {
    const fallback = new EnhancedContentExtractor({ withHttp: fn => fn(), withPage: (fn, budget, onStart) => { onStart?.(); return budget.wait(fn(page)); } });
    fallback.extractWithAxios = async (_options, state) => { state.httpStatus = 403; state.contentType = 'text/html'; return ''; };
    if (parseFails) fallback.parseContent = () => { throw new Error('parse boom'); };
    return fallback.extractContent({ url: 'https://example.org/file' });
  };
  const pdfDownload = await viaBrowser(browserPage({ response: 'application/pdf', download: true, failing: true }));
  assert.deepEqual([pdfDownload.status, pdfDownload.httpStatus, pdfDownload.contentType], ['unsupported_media', 200, 'application/pdf']);
  const silentDownload = await viaBrowser(browserPage({ download: true, failing: true }));
  assert.deepEqual([silentDownload.status, silentDownload.httpStatus, silentDownload.contentType], ['unsupported_media', undefined, undefined]);
  assert.equal(silentDownload.error, 'Unsupported media: unknown (download started)');
  const aborted = await viaBrowser(browserPage({ failing: true }));
  assert.equal(aborted.status, 'http_error');
  assert.equal(aborted.attempts.at(-1).error, 'page.goto: net::ERR_ABORTED at https://example.org/file');
  const browserConversion = await viaBrowser(browserPage({}), true);
  assert.deepEqual([browserConversion.status, browserConversion.error], ['conversion_error', 'parse boom']);
  assert.deepEqual(browserConversion.attempts.map(a => a.transport), ['http', 'browser']);
}
process.stdout.write('declared charsets, read-limit facts, downloads, error lines and conversion errors: passed\n');

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
assert.match(withContent, /selected=5; candidates_attempted=5; source_read_attempts=6; http_attempts=5; browser_attempts=1; returned=5/);
assert.doesNotMatch(withContent, /transport_retries/);
assert.match(withContent, /^Statistics scope: source_read_attempts counts started HTTP and browser reads .*Redirects followed within one HTTP read are not counted separately\. parsed_count is the rows an engine returned before cross-engine deduplication/m);
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

// FA07/FA08: each started attempt keeps its own facts; the summary is the last started attempt.
{
  const { chromium } = await import('playwright');
  const { BrowserPool, CallBudget } = await import('../dist/browser-pool.js');
  const fakePage = { on: () => undefined, off: () => undefined, mainFrame: () => undefined,
    goto: async () => { throw new Error('page.goto: net::ERR_CONNECTION_RESET'); }, url: () => 'https://example.org/p' };
  const stubPool = { withHttp: fn => fn(), withPage: (fn, budget, onStart) => { onStart?.(); return budget.wait(fn(fakePage)); } };
  const httpThen = (pool, http) => {
    const reader = new EnhancedContentExtractor(pool);
    reader.extractWithAxios = http;
    return reader;
  };
  // HTTP empty text, then the browser fails: the summary has no HTTP lengths; both attempts keep their facts.
  const emptyThenFail = await httpThen(stubPool, async (_options, state) => {
    state.httpStatus = 200; state.contentType = 'text/html'; state.finalUrl = 'https://example.org/p?http'; return '';
  }).extractContent({ url: 'https://example.org/p' });
  assert.equal(emptyThenFail.status, 'http_error');
  assert.equal(emptyThenFail.originalLength, undefined);
  assert.equal(emptyThenFail.httpStatus, undefined);
  assert.equal(emptyThenFail.error, 'page.goto: net::ERR_CONNECTION_RESET');
  assert.deepEqual(emptyThenFail.attempts.map(a => [a.transport, a.outcome, a.status, a.originalLength]), [['http', 'empty_text', 200, 0], ['browser', 'http_error', undefined, undefined]]);
  const emptyText = formatPageRead(emptyThenFail);
  assert.match(emptyText, /- http: status=200; read_status=empty_text; content_type=text\/html; final_url=https:\/\/example\.org\/p\?http; markdown_length=0\/0\n- browser: status=unknown; read_status=http_error; error=page\.goto: net::ERR_CONNECTION_RESET/);
  assert.doesNotMatch(emptyText, /Markdown length:/);
  // HTTP 403, then an empty browser read: the summary error is not the replaced 403.
  const deniedThenEmpty = new EnhancedContentExtractor({ withHttp: fn => fn(), withPage: (fn, budget, onStart) => {
    onStart?.();
    return budget.wait(fn({ ...fakePage, goto: async () => ({ status: () => 200, headers: () => ({ 'content-type': 'text/plain' }) }),
      title: async () => '', locator: () => ({ innerText: async () => '' }) }));
  } });
  deniedThenEmpty.extractWithAxios = async (_options, state) => {
    state.httpStatus = 403;
    throw Object.assign(new Error('Request failed with status code 403'), { response: { status: 403, headers: { 'content-type': 'text/html' } } });
  };
  const denied = await deniedThenEmpty.extractContent({ url: 'https://example.org/p' });
  assert.equal(denied.status, 'empty_text');
  assert.equal(denied.error, undefined);
  assert.doesNotMatch(formatPageRead(denied), /Read error/);
  assert.deepEqual(denied.attempts.map(a => [a.transport, a.status, a.error ?? null]), [['http', 403, 'Request failed with status code 403'], ['browser', 200, null]]);
  // A launch failure is a started browser attempt with its reason; a fallback that only queued is not.
  const launch = chromium.launch;
  try {
    chromium.launch = async () => { throw new Error('browserType.launch: injected launch failure'); };
    const launchReader = httpThen(new BrowserPool(), async () => '');
    const launchRead = await launchReader.extractContent({ url: 'https://example.org/p' });
    assert.deepEqual(launchRead.attempts.map(a => [a.transport, a.error ?? null]), [['http', null], ['browser', 'browserType.launch: injected launch failure']]);
    assert.match(formatSearchResponse('x', [{ title: 't', url: 'https://example.org/p', description: '', read: launchRead }], [], true), /source_read_attempts=2; http_attempts=1; browser_attempts=1/);
    let release;
    const held = new Promise(resolve => { release = resolve; });
    chromium.launch = async () => ({ isConnected: () => true, version: () => '777.0.0.0', newContext: async () => ({ newPage: async () => ({}), close: async () => undefined }), close: async () => undefined });
    const busyPool = new BrowserPool();
    const busy = [busyPool.withPage(() => held), busyPool.withPage(() => held)];
    const queueBudget = new CallBudget(60);
    const queued = await httpThen(busyPool, async () => '').extractContent({ url: 'https://example.org/p', budget: queueBudget });
    queueBudget.dispose();
    release();
    await Promise.all(busy);
    await busyPool.closeAll();
    assert.deepEqual(queued.attempts.map(a => a.transport), ['http']);
    assert.equal(queued.status, 'empty_text');
    assert.deepEqual(queued.notStarted, { transport: 'browser', reason: 'Call deadline exceeded' });
    assert.match(formatPageRead(queued), /- browser: not started \(Call deadline exceeded\)/);
  } finally { chromium.launch = launch; }
  // targetCount reads only the first candidates; the others stay, unread.
  const counted = [];
  const targetReader = httpThen(stubPool, async options => { counted.push(options.url); return 'text'; });
  targetReader.extractWithBrowser = async () => { throw new Error('no fallback expected'); };
  const five = ['a', 'b', 'c', 'd', 'e'].map(id => ({ title: id, url: `https://example.org/${id}`, description: '' }));
  const targeted = await targetReader.extractContentForResults(five, 2);
  assert.deepEqual(counted, ['https://example.org/a', 'https://example.org/b']);
  assert.deepEqual(targeted.map(r => r.url), five.map(r => r.url));
  assert.deepEqual(targeted.map(r => r.read?.status ?? 'not_attempted'), ['text', 'text', 'not_attempted', 'not_attempted', 'not_attempted']);
  const targetText = formatSearchResponse('x', targeted, [], true);
  assert.match(targetText, new RegExp(`candidates_attempted=2; source_read_attempts=${counted.length}; http_attempts=2; browser_attempts=0; returned=5`));
}
process.stdout.write('per-attempt facts, started-attempt counting, targetCount and statistics scope: passed\n');
