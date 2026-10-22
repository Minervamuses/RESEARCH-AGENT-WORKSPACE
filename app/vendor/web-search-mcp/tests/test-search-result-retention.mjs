// Offline regression for SearchEngine.search(): strategy B retains candidates and execution facts.
// Usage: node tests/test-search-result-retention.mjs [dist-directory]
// Network, TLS, fetch and Playwright browser launches are blocked; engines are stubbed.
import assert from 'node:assert/strict';
import net from 'node:net';
import path from 'node:path';
import tls from 'node:tls';
import { fileURLToPath, pathToFileURL } from 'node:url';

net.Socket.prototype.connect = function () { throw new Error('network blocked in offline test'); };
tls.connect = () => { throw new Error('TLS blocked in offline test'); };
globalThis.fetch = async () => { throw new Error('fetch blocked in offline test'); };

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(process.argv[2] ?? path.join(here, '..', 'dist'));
const playwright = await import(pathToFileURL(path.join(dist, '..', 'node_modules', 'playwright', 'index.mjs')).href);
for (const browserType of [playwright.chromium, playwright.firefox, playwright.webkit]) {
  browserType.launch = async () => { throw new Error('browser launch blocked in offline test'); };
}
const { BrowserPool, CallBudget } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);

const logs = [];
console.log = (...args) => logs.push(args.join(' '));
console.error = (...args) => logs.push(args.join(' '));

const record = (title, id) => ({ title, description: '', url: `https://example.org/${id}` });
function engineWith({ google = [], bing = [] } = {}) {
  const engine = new SearchEngine();
  const attempts = [];
  for (const [method, name, value] of [
    ['tryGoogleSearch', 'google', google],
    ['tryBingSearch', 'bing', bing],
  ]) {
    engine[method] = async () => {
      attempts.push(name);
      if (value instanceof Error) throw value;
      return value;
    };
  }
  return { engine, attempts };
}
const cases = [];
const check = (name, fn) => cases.push({ name, fn });
const { formatSearchResponse } = await import(pathToFileURL(path.join(dist, 'utils.js')).href);

check('strategy B: a full Google batch never calls Bing', async () => {
  const { engine, attempts } = engineWith({ google: ['1', '2', '3', '4', '5'].map(id => record(id, id)), bing: [record('bing', 'b')] });
  const result = await engine.search({ query: 'x', numResults: 5 });
  assert.equal(result.results.length, 5);
  assert.deepEqual(attempts, ['google']);
  assert.equal(result.engines[1].status, 'strategy_stopped');
  assert.equal(result.engines[1].attempted, false);
});
check('strategy B fills five stable candidates and merges duplicate provenance', async () => {
  const { engine, attempts } = engineWith({
    google: [record('first', '1'), record('second', '2')],
    bing: [record('changed duplicate', '2'), record('third', '3'), record('fourth', '4'), record('fifth', '5')],
  });
  const result = await engine.search({ query: '中文', numResults: 5 });
  assert.deepEqual(result.results.map(r => r.title), ['first', 'second', 'third', 'fourth', 'fifth']);
  assert.deepEqual(result.results[1].sourceEngines, ['Google', 'Bing']);
  assert.deepEqual(attempts, ['google', 'bing']);
  assert.ok(result.results.every(r => r.read === undefined));
});
for (const blocked of ['Google returned HTTP 429', 'Google redirected to /sorry/index (HTTP 200)']) {
  check(`a blocked Google (${blocked}) is filled by Bing and keeps its facts`, async () => {
    const { engine, attempts } = engineWith({ google: new Error(blocked), bing: [record('one', '1'), record('two', '2')] });
    const result = await engine.search({ query: 'x', numResults: 2 });
    assert.deepEqual(attempts, ['google', 'bing']);
    assert.deepEqual(result.results.map(r => r.sourceEngines), [['Bing'], ['Bing']]);
    assert.equal(result.engines[0].status, 'error');
    assert.equal(result.engines[0].error, blocked);
    assert.ok(formatSearchResponse('x', result.results, result.engines).includes(`- Google: attempted=true; attempts=1; parsed_count=0; status=error; error=${blocked}`));
  });
}
check('later failures retain earlier candidates and expose errors', async () => {
  const { engine } = engineWith({ google: [record('one', '1'), record('two', '2')], bing: new Error('Bing returned HTTP 403') });
  const result = await engine.search({ query: 'AI' });
  assert.equal(result.results.length, 2);
  assert.equal(result.engines[1].status, 'error');
  assert.equal(result.engines[1].error, 'Bing returned HTTP 403');
});
check('all failures and all zero parses remain distinguishable', async () => {
  const empty = await engineWith().engine.search({ query: 'x' });
  const error = new Error('unavailable');
  const failed = await engineWith({ google: error, bing: error }).engine.search({ query: 'x' });
  assert.ok(empty.engines.every(e => e.status === 'zero_parsed'));
  assert.ok(failed.engines.every(e => e.status === 'error'));
});
for (const query of ['中文查詢', 'AI', 'sports', 'weather']) {
  check(`query ${query} has no semantic scoring`, async () => {
    const { engine, attempts } = engineWith({ google: [record('unrelated', '1')], bing: [record('other', '2')] });
    assert.equal(engine.assessResultQuality, undefined);
    const result = await engine.search({ query, numResults: 2 });
    assert.deepEqual(result.results.map(r => r.title), ['unrelated', 'other']);
    assert.deepEqual(attempts, ['google', 'bing']);
  });
}
check('URL handling validates schemes and preserves query/encoding', async () => {
  const { engine } = engineWith({ google: [
    record('encoded', 'a%252Fb?q=1&tracking=2'),
    { ...record('bad', 'bad'), url: 'javascript:alert(1)' },
    record('distinct query', 'a%252Fb?q=2&tracking=2'),
  ] });
  const result = await engine.search({ query: 'x' });
  assert.equal(result.results.length, 2);
  assert.match(result.results[0].url, /a%252Fb\?q=1&tracking=2$/);
});

// Engine methods with a fake Playwright browser: observed HTTP facts, no retry, no second browser.
const GOOGLE_HTML = `<html><body><div id="search"><div id="rso">
<div class="MjjYud"><div><a href="/goto?url=CAESabc&amp;x=1"><h3>Wrapped result</h3></a></div><div class="VwiC3b">Wrapped snippet.</div></div>
<div class="MjjYud"><a href="https://direct.example/page"><h3>Direct result</h3></a></div>
<div class="MjjYud"><a href="https://support.google.com/x"><h3></h3></a><div data-sncf="1">No title snippet.</div></div>
</div></div><div id="rhs"><a href="https://side.example/"><h3>Side panel</h3></a></div></body></html>`;
function fakeBrowser({ status = 200, finalUrl, html = '<html></html>', events, gotos = [] }) {
  let current;
  const page = {
    goto: async (url, options) => { events.push('goto'); gotos.push({ url, options }); current = finalUrl ?? url; return { status: () => status }; },
    waitForSelector: async () => { events.push('wait'); },
    content: async () => { events.push('content'); return html; },
    url: () => current,
  };
  const context = { newPage: async () => page, close: async () => events.push('context-close') };
  return { isConnected: () => true, version: () => '777.0.0.0', newContext: async () => context, close: async () => events.push('browser-close') };
}
async function withFakeBrowser(options, fn) {
  const events = [];
  const launch = playwright.chromium.launch;
  playwright.chromium.launch = async () => { events.push('launch'); return fakeBrowser({ ...options, events }); };
  const pool = new BrowserPool();
  const budget = new CallBudget(1000);
  try { return await fn(new SearchEngine(pool), budget, events); } finally {
    budget.dispose();
    await pool.closeAll();
    playwright.chromium.launch = launch;
  }
}
check('Google HTTP 429 fails at once without retry or a second browser', async () => {
  await withFakeBrowser({ status: 429 }, async (engine, budget, events) => {
    await assert.rejects(engine.tryGoogleSearch('alpha', 5, 1000, undefined, budget), /^Error: Google returned HTTP 429$/);
    assert.deepEqual(events, ['launch', 'goto', 'context-close']);
  });
});
check('Google /sorry/ redirect fails at once with the final path', async () => {
  await withFakeBrowser({ finalUrl: 'https://www.google.com/sorry/index?continue=x' }, async (engine, budget, events) => {
    await assert.rejects(engine.tryGoogleSearch('alpha', 5, 1000, undefined, budget), /Google redirected to \/sorry\/index \(HTTP 200\)/);
    assert.deepEqual(events, ['launch', 'goto', 'context-close']);
  });
});
check('Google HTTP 200 waits for results and parses the main results area', async () => {
  await withFakeBrowser({ html: GOOGLE_HTML }, async (engine, budget, events) => {
    const parsed = await engine.tryGoogleSearch('alpha', 5, 1000, undefined, budget);
    assert.deepEqual(events, ['launch', 'goto', 'wait', 'content', 'context-close']);
    assert.deepEqual(parsed.map(r => [r.title, r.url, r.observedUrl, r.description]), [
      ['Wrapped result', 'https://www.google.com/goto?url=CAESabc&x=1', '/goto?url=CAESabc&x=1', 'Wrapped snippet.'],
      ['Direct result', 'https://direct.example/page', 'https://direct.example/page', ''],
      ['', 'https://support.google.com/x', 'https://support.google.com/x', 'No title snippet.'],
    ]);
  });
});
check('search() keeps a relative Google wrapper href as an absolute candidate', async () => {
  await withFakeBrowser({ html: GOOGLE_HTML }, async (engine, budget) => {
    engine.tryBingSearch = async () => [];
    const result = await engine.search({ query: 'alpha', numResults: 5, budget });
    assert.equal(result.results[0].url, 'https://www.google.com/goto?url=CAESabc&x=1');
    assert.equal(result.results[0].observedUrl, '/goto?url=CAESabc&x=1');
    assert.equal(result.results.length, 3);
    assert.deepEqual(result.engines.map(e => e.status), ['completed', 'zero_parsed']);
  });
});
check('query language selects Google hl and Bing setlang/cc, at overridable addresses', async () => {
  const { queryMarket } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
  assert.deepEqual(queryMarket('機器學習 過擬合'), { googleHl: 'zh-TW', bingSetlang: 'zh-Hant', bingCc: 'TW' });
  assert.deepEqual(queryMarket('python asyncio'), { googleHl: 'en', bingSetlang: 'en', bingCc: 'US' });
  const saved = [SearchEngine.googleSearchUrl, SearchEngine.bingSearchUrl];
  try {
    for (const [query, hl, setlang, cc] of [['颱風 消息', 'zh-TW', 'zh-Hant', 'TW'], ['typhoon news', 'en', 'en', 'US']]) {
      const gotos = [];
      await withFakeBrowser({ gotos }, async (engine, budget) => {
        await engine.tryGoogleSearch(query, 4, 1000, undefined, budget);
        await engine.tryBingSearch(query, 4, 1000, undefined, budget);
      });
      const [google, bing] = gotos.map(g => new URL(g.url));
      assert.equal(`${google.origin}${google.pathname}`, 'https://www.google.com/search');
      assert.deepEqual([google.searchParams.get('q'), google.searchParams.get('hl'), google.searchParams.get('num')], [query, hl, '4']);
      assert.equal(`${bing.origin}${bing.pathname}`, 'https://www.bing.com/search');
      assert.deepEqual([bing.searchParams.get('q'), bing.searchParams.get('count'), bing.searchParams.get('setlang'), bing.searchParams.get('cc')], [query, '4', setlang, cc]);
      assert.equal(bing.searchParams.get('cvid'), null);
    }
    SearchEngine.googleSearchUrl = 'http://127.0.0.1:9/fake-google';
    SearchEngine.bingSearchUrl = 'http://127.0.0.1:9/fake-bing';
    const gotos = [];
    await withFakeBrowser({ gotos }, async (engine, budget) => {
      await engine.tryGoogleSearch('x', 1, 1000, undefined, budget);
      await engine.tryBingSearch('x', 1, 1000, undefined, budget);
    });
    assert.deepEqual(gotos.map(g => g.url.split('?')[0]), ['http://127.0.0.1:9/fake-google', 'http://127.0.0.1:9/fake-bing']);
  } finally { [SearchEngine.googleSearchUrl, SearchEngine.bingSearchUrl] = saved; }
});

check('both search tools share distinguishable engine and provenance text', async () => {
  const error = new Error('HTTP 429');
  const failed = await engineWith({ google: error, bing: error }).engine.search({ query: 'x' });
  const empty = await engineWith().engine.search({ query: 'x' });
  const partial = await engineWith({ google: [record('one', '1')], bing: error }).engine.search({ query: 'x' });
  const render = r => formatSearchResponse('x', r.results, r.engines);
  const texts = [failed, empty, partial].map(render);
  assert.equal(new Set(texts).size, 3);
  assert.match(texts[0], /All attempted engines failed/);
  assert.match(texts[1], /status=zero_parsed/);
  assert.match(texts[2], /Source engines: Google/);
  assert.match(texts[2], /- Bing: attempted=true; attempts=1; parsed_count=0; status=error/);
  const { readFile } = await import('node:fs/promises');
  const source = await readFile(path.join(dist, '..', 'src', 'index.ts'), 'utf8');
  assert.equal((source.match(/const responseText = formatSearchResponse\(/g) ?? []).length, 2);
  assert.match(source, /numResults: limit/);
});

check('strict content limits, deployment precedence, booleans and Unicode', async () => {
  const { validateSearchInput, resolveContentLimit, truncateMarkdown } = await import(pathToFileURL(path.join(dist, 'utils.js')).href);
  const { EnhancedContentExtractor } = await import(pathToFileURL(path.join(dist, 'enhanced-content-extractor.js')).href);
  const previous = process.env.MAX_CONTENT_LENGTH;
  try {
    delete process.env.MAX_CONTENT_LENGTH;
    assert.deepEqual(validateSearchInput({ query: 'x' }), { query: 'x', limit: 5, includeContent: true, maxContentLength: 10000 });
    process.env.MAX_CONTENT_LENGTH = '9';
    for (const value of [undefined, 0, '0']) assert.equal(resolveContentLimit(value), 9);
    for (const value of [7, '7']) {
      const args = validateSearchInput({ query: 'x', maxContentLength: value, includeContent: 'false' });
      assert.equal(args.maxContentLength, 7);
      assert.equal(args.includeContent, false);
      const extractor = new EnhancedContentExtractor();
      const text = '😀中文😀abcXYZ';
      extractor.extractWithAxios = async () => text;
      assert.equal((await extractor.extractContent({ url: 'https://example.org', maxContentLength: args.maxContentLength })).content, truncateMarkdown(text, 7).content);
    }
    for (const value of [10001, -1, 1.5, NaN, '7junk', '7.5', '']) {
      assert.throws(() => resolveContentLimit(value), /integer between 0 and 10000/);
    }
    assert.throws(() => validateSearchInput({ query: 'x', includeContent: 'yes' }), /true or false/);
    assert.throws(() => validateSearchInput({ query: 'x', limit: '2junk' }), /integer/);
    process.env.MAX_CONTENT_LENGTH = '10001';
    assert.throws(() => resolveContentLimit(7), /MAX_CONTENT_LENGTH/);
    const { readFile } = await import('node:fs/promises');
    const source = await readFile(path.join(dist, '..', 'src', 'index.ts'), 'utf8');
    assert.equal((source.match(/transform\(resolveContentLimit\)/g) ?? []).length, 2);
    assert.match(source, /extractContentForResults\(searchResponse.results, limit, maxContentLength, budget\)/);
    assert.doesNotMatch(source, /isLikelyLlama|isLikelyRobustModel|parseInt\(|0 = no limit/);
  } finally {
    if (previous === undefined) delete process.env.MAX_CONTENT_LENGTH;
    else process.env.MAX_CONTENT_LENGTH = previous;
  }
});

check('call expiry preserves fixed candidates and stops remaining engines', async () => {
  const { engine, attempts } = engineWith({ google: [record('known', 'known')] });
  engine.tryBingSearch = async (_q, _n, _timeout, _state, budget) => {
    attempts.push('bing');
    return budget.wait(new Promise(() => {}));
  };
  const budget = new CallBudget(20);
  const result = await engine.search({ query: 'x', budget });
  budget.dispose();
  assert.equal(result.results[0].title, 'known');
  assert.deepEqual(attempts, ['google', 'bing']);
  assert.equal(result.engines[1].status, 'error');
  assert.match(result.engines[1].error, /deadline/);
  const stuck = engineWith({ bing: [record('late', 'late')] });
  stuck.engine.tryGoogleSearch = async (_q, _n, _timeout, _state, budget) => {
    stuck.attempts.push('google');
    return budget.wait(new Promise(() => {}));
  };
  const short = new CallBudget(20);
  const stopped = await stuck.engine.search({ query: 'x', budget: short });
  short.dispose();
  assert.deepEqual(stuck.attempts, ['google']);
  assert.equal(stopped.results.length, 0);
  assert.equal(stopped.engines[1].attempted, false);
  assert.match(stopped.engines[1].error, /deadline/);
});

check('parsers keep organic results only, short snippets, unknown titles and the actual page base', async () => {
  const engine = new SearchEngine();
  const sidebar = '<div id="b_context"><div class="b_card"><h2><a href="https://typhoon.example/">颱風消息</a></h2></div>'
    + '<div class="b_result"><h2><a href="https://module.example/">Module</a></h2></div></div>';
  const html = `<ol id="b_results"><li class="b_algo"><h2><a href="../item?q=%252F">AI</a></h2><div class="b_caption"><p>AI.</p></div></li>`
    + `<li class="b_ans"><h2><a href="https://answer.example/">Answer</a></h2></li></ol>${sidebar}`;
  const parsed = engine.parseBingResults(html, 5, 'https://www.bing.com/search/path/');
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0].description, 'AI.');
  assert.equal(parsed[0].url, 'https://www.bing.com/search/item?q=%252F');
  assert.equal(parsed[0].observedUrl, '../item?q=%252F');
  assert.deepEqual(engine.parseBingResults(`<ol id="b_results"><li class="b_ans"><h2><a href="https://answer.example/">Answer</a></h2></li></ol>${sidebar}`, 5), []);
  const [missing] = engine.parseBingResults('<ol id="b_results"><li class="b_algo"><h2><a href="/unknown"></a></h2><p>Known snippet.</p></li></ol>', 1);
  assert.equal(missing.title, '');
  assert.equal(missing.description, 'Known snippet.');
  assert.equal(missing.url, 'https://www.bing.com/unknown');
  const [based] = engine.parseGoogleResults('<base href="/docs/"><div id="search"><a href="next"><h3>T</h3></a></div>', 1, 'https://www.google.com/search?q=x');
  assert.equal(based.url, 'https://www.google.com/docs/next');
  assert.deepEqual(engine.parseGoogleResults('<div id="rhs"><a href="https://side.example/"><h3>Side</h3></a></div>', 5), []);
});

let failed = 0;
for (const { name, fn } of cases) {
  logs.length = 0;
  try {
    await fn();
    process.stdout.write(`ok - ${name}\n`);
  } catch (error) {
    failed += 1;
    process.stdout.write(`not ok - ${name}\n${error.stack}\n--- engine log ---\n${logs.join('\n')}\n`);
  }
}
process.stdout.write(`${cases.length - failed}/${cases.length} passed (${dist})\n`);
process.exitCode = failed === 0 ? 0 : 1;
