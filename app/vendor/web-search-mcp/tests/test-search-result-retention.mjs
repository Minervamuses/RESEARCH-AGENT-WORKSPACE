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
const { BrowserPool, CallBudget, OPERATION_TIMEOUTS } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
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
    engine[method] = async (_query, _n, _timeout, _state, _budget, admit) => {
      attempts.push(name);
      if (value instanceof Error) throw value;
      await admit(value, { url: () => `https://stub.example/${name}` });
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
// wrappers maps an absolute wrapper URL to { to, delay } (redirect), { stay }, { hang } or { fail }.
function fakeBrowser({ status = 200, finalUrl, html = '<html></html>', pages = {}, wrappers = {}, events, gotos = [] }) {
  let current;
  const listeners = new Set();
  const mainFrame = {};
  const emit = url => { for (const listener of [...listeners]) listener({ isNavigationRequest: () => true, frame: () => mainFrame, url: () => url }); };
  const page = {
    on: (event, listener) => { if (event === 'request') listeners.add(listener); },
    off: (event, listener) => { listeners.delete(listener); },
    mainFrame: () => mainFrame,
    goto: async (url, options) => {
      events.push('goto'); gotos.push({ url, options });
      const behavior = wrappers[url];
      if (!behavior) { current = finalUrl ?? url; return { status: () => status }; }
      emit(url);
      if (behavior.fail) throw new Error(behavior.fail);
      if (behavior.hang) {
        return new Promise((_resolve, reject) => setTimeout(() => reject(Object.assign(new Error('Timeout'), { name: 'TimeoutError' })), options.timeout));
      }
      if (behavior.to) setTimeout(() => emit(behavior.to), behavior.delay ?? 0);
      return { status: () => 200 };
    },
    waitForSelector: async () => { events.push('wait'); },
    content: async () => { events.push('content'); return Object.entries(pages).find(([prefix]) => current.startsWith(prefix))?.[1] ?? html; },
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
check('search() resolves a relative Google wrapper by navigation, referred by the search page', async () => {
  const wrapper = 'https://www.google.com/goto?url=CAESabc&x=1';
  const gotos = [];
  await withFakeBrowser({ html: GOOGLE_HTML, gotos, wrappers: { [wrapper]: { to: 'https://target.example/a?b=%252F', delay: 5 } } }, async (engine, budget) => {
    engine.tryBingSearch = async () => [];
    const result = await engine.search({ query: 'alpha', numResults: 5, budget });
    const [first, ...rest] = result.results;
    assert.equal(first.url, 'https://target.example/a?b=%252F');
    assert.equal(first.observedUrl, '/goto?url=CAESabc&x=1');
    assert.equal(first.resolution.wrapperUrl, wrapper);
    assert.equal(first.resolution.outcome, 'resolved');
    assert.ok(Number.isInteger(first.resolution.ms) && first.resolution.ms >= 0);
    // support.google.com and direct links are ordinary results, never navigated.
    assert.deepEqual(rest.map(r => [r.url, r.resolution]), [['https://direct.example/page', undefined], ['https://support.google.com/x', undefined]]);
    assert.deepEqual(gotos.slice(1).map(g => [g.url, g.options.referer, g.options.waitUntil]), [[wrapper, gotos[0].url, 'commit']]);
    assert.deepEqual(result.engines.map(e => e.status), ['completed', 'zero_parsed']);
  });
});
const googlePage = hrefs => `<div id="search">${hrefs.map((href, i) => `<div><a href="${href}"><h3>R${i + 1}</h3></a></div>`).join('')}</div>`;
check('unresolved wrappers keep the wrapper URL with outcome and reason', async () => {
  const cap = OPERATION_TIMEOUTS.linkResolve;
  OPERATION_TIMEOUTS.linkResolve = 60;
  const base = 'https://www.google.com/goto?k=';
  try {
    await withFakeBrowser({
      html: googlePage(['/goto?k=stay', '/goto?k=hang', '/goto?k=fail', '/goto?k=ok']),
      wrappers: { [`${base}stay`]: { stay: true }, [`${base}hang`]: { hang: true }, [`${base}fail`]: { fail: 'net::ERR_NAME_NOT_RESOLVED at x\nCall log: y' }, [`${base}ok`]: { to: 'https://ok.example/' } },
    }, async (engine, budget) => {
      engine.tryBingSearch = async () => [];
      const result = await engine.search({ query: 'x', numResults: 4, budget });
      assert.deepEqual(result.results.map(r => [r.url, r.resolution.outcome]), [
        [`${base}stay`, 'stayed_on_engine_host'], [`${base}hang`, 'timeout'], [`${base}fail`, 'failed'], ['https://ok.example/', 'resolved'],
      ]);
      assert.match(result.results[0].resolution.reason, /responded but no navigation left www\.google\.com within 60 ms/);
      assert.match(result.results[1].resolution.reason, /did not respond within 60 ms/);
      assert.equal(result.results[2].resolution.reason, 'net::ERR_NAME_NOT_RESOLVED at x');
    });
  } finally { OPERATION_TIMEOUTS.linkResolve = cap; }
});
check('near the call deadline wrappers stay candidates and the rest are not started', async () => {
  const base = 'https://www.google.com/goto?k=';
  const gotos = [];
  const keys = ['a', 'b', 'c', 'd'];
  const begin = performance.now();
  const events = [];
  const launch = playwright.chromium.launch;
  playwright.chromium.launch = async () => fakeBrowser({
    html: googlePage(keys.map(k => `/goto?k=${k}`)), events, gotos, wrappers: Object.fromEntries(keys.map(k => [`${base}${k}`, { hang: true }])),
  });
  const pool = new BrowserPool();
  const budget = new CallBudget(150);
  try {
    const result = await new SearchEngine(pool).search({ query: 'x', numResults: 4, budget });
    assert.ok(performance.now() - begin < 1000);
    assert.deepEqual(result.results.map(r => r.url), keys.map(k => `${base}${k}`));
    const outcomes = result.results.map(r => r.resolution.outcome);
    assert.equal(outcomes[0], 'timeout');
    assert.equal(outcomes.at(-1), 'not_started');
    assert.ok(outcomes.every(o => ['timeout', 'not_started'].includes(o)), outcomes.join());
    assert.ok(gotos.length - 1 <= 2, `wrapper navigations after the deadline: ${gotos.length - 1}`);
    assert.match(result.results.at(-1).resolution.reason, /deadline/);
  } finally {
    budget.dispose();
    await pool.closeAll();
    playwright.chromium.launch = launch;
  }
});
check('only the needed wrappers are resolved; a duplicate lets the next one in, in order', async () => {
  const base = 'https://www.google.com/goto?n=';
  const wrappers = Object.fromEntries([1, 2, 3, 4, 5, 6, 7, 8].map(n => [`${base}${n}`, { to: `https://t.example/${n === 3 ? 1 : n}` }]));
  const gotos = [];
  await withFakeBrowser({ html: googlePage([1, 2, 3, 4, 5, 6, 7, 8].map(n => `/goto?n=${n}`)), wrappers, gotos }, async (engine, budget) => {
    const result = await engine.search({ query: 'x', numResults: 5, budget });
    assert.deepEqual(result.results.map(r => r.url), [1, 2, 4, 5, 6].map(n => `https://t.example/${n}`));
    assert.deepEqual(gotos.slice(1).map(g => g.url), [1, 2, 3, 4, 5, 6].map(n => `${base}${n}`));
    assert.deepEqual(result.results[0].sourceEngines, ['Google']);
    assert.equal(result.engines[0].parsedCount, 8);
  });
});
const BING_WRAPPED = '<ol id="b_results"><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=1">T</a></h2></li>'
  + '<li class="b_algo"><h2><a href="https://www.bing.com/ck/a?u=2">U</a></h2></li></ol>';
const crossEngine = {
  pages: { 'https://www.google.com/search': googlePage(['/goto?g=1']), 'https://www.bing.com/search': BING_WRAPPED },
  wrappers: {
    'https://www.google.com/goto?g=1': { to: 'https://same.example/target' },
    'https://www.bing.com/ck/a?u=1': { to: 'https://same.example/target' },
    'https://www.bing.com/ck/a?u=2': { to: 'https://other.example/' },
  },
};
check('Google and Bing wrappers resolving to one URL merge into one candidate', async () => {
  await withFakeBrowser(crossEngine, async (engine, budget) => {
    const result = await engine.search({ query: 'x', numResults: 2, budget });
    assert.deepEqual(result.results.map(r => [r.url, r.sourceEngines]), [
      ['https://same.example/target', ['Google', 'Bing']], ['https://other.example/', ['Bing']],
    ]);
  });
});
check('one page slot (MAX_CONCURRENT_PAGES=1) searches and resolves without deadlock', async () => {
  const previous = process.env.MAX_CONCURRENT_PAGES;
  process.env.MAX_CONCURRENT_PAGES = '1';
  try {
    await withFakeBrowser(crossEngine, async (engine, budget) => {
      const result = await Promise.race([
        engine.search({ query: 'x', numResults: 2, budget }),
        new Promise((_resolve, reject) => setTimeout(() => reject(new Error('deadlock')), 900)),
      ]);
      assert.deepEqual(result.results.map(r => r.url), ['https://same.example/target', 'https://other.example/']);
    });
  } finally {
    if (previous === undefined) delete process.env.MAX_CONCURRENT_PAGES; else process.env.MAX_CONCURRENT_PAGES = previous;
  }
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
  const parsed = engine.parseBingResults(html, 'https://www.bing.com/search/path/');
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0].description, 'AI.');
  assert.equal(parsed[0].url, 'https://www.bing.com/search/item?q=%252F');
  assert.equal(parsed[0].observedUrl, '../item?q=%252F');
  assert.deepEqual(engine.parseBingResults(`<ol id="b_results"><li class="b_ans"><h2><a href="https://answer.example/">Answer</a></h2></li></ol>${sidebar}`), []);
  const [missing] = engine.parseBingResults('<ol id="b_results"><li class="b_algo"><h2><a href="/unknown"></a></h2><p>Known snippet.</p></li></ol>');
  assert.equal(missing.title, '');
  assert.equal(missing.description, 'Known snippet.');
  assert.equal(missing.url, 'https://www.bing.com/unknown');
  const [based] = engine.parseGoogleResults('<base href="/docs/"><div id="search"><a href="next"><h3>T</h3></a></div>', 'https://www.google.com/search?q=x');
  assert.equal(based.url, 'https://www.google.com/docs/next');
  assert.deepEqual(engine.parseGoogleResults('<div id="rhs"><a href="https://side.example/"><h3>Side</h3></a></div>'), []);
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
