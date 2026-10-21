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

const record = (title, id) => ({ title, description: '', url: `https://example.org/${id}`, timestamp: 'fixed' });
function engineWith({ bing = [], ddg = [], brave = [] } = {}) {
  const engine = new SearchEngine();
  const attempts = [];
  for (const [method, name, value] of [
    ['tryBrowserBingSearch', 'bing', bing],
    ['tryDuckDuckGoSearch', 'ddg', ddg],
    ['tryBrowserBraveSearch', 'brave', brave],
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
const configure = () => {};

check('strategy B fills five stable candidates and merges duplicate provenance', async () => {
  const { engine, attempts } = engineWith({
    bing: [record('first', '1'), record('second', '2')],
    ddg: [record('changed duplicate', '2'), record('third', '3'), record('fourth', '4'), record('fifth', '5')],
  });
  const result = await engine.search({ query: '中文', numResults: 5 });
  assert.deepEqual(result.results.map(r => r.title), ['first', 'second', 'third', 'fourth', 'fifth']);
  assert.deepEqual(result.results[1].sourceEngines, ['Browser Bing', 'Axios DuckDuckGo']);
  assert.deepEqual(attempts, ['bing', 'ddg']);
  assert.equal(result.engines[2].status, 'strategy_stopped');
  assert.equal(result.engines[2].attempted, false);
  assert.ok(result.results.every(r => r.fetchStatus === 'not_requested'));
});
check('later failures retain earlier candidates and expose errors', async () => {
  const { engine } = engineWith({ bing: [record('one', '1'), record('two', '2')], ddg: new Error('HTTP 403'), brave: new Error('HTTP 429') });
  const result = await engine.search({ query: 'AI' });
  assert.equal(result.results.length, 2);
  assert.equal(result.engines[1].error, 'HTTP 403');
  assert.equal(result.engines[2].status, 'error');
});
check('all failures and all zero parses remain distinguishable', async () => {
  const empty = await engineWith().engine.search({ query: 'x' });
  const error = new Error('unavailable');
  const failed = await engineWith({ bing: error, ddg: error, brave: error }).engine.search({ query: 'x' });
  assert.ok(empty.engines.every(e => e.status === 'zero_parsed'));
  assert.ok(failed.engines.every(e => e.status === 'error'));
});
for (const query of ['中文查詢', 'AI', 'sports', 'weather']) {
  check(`query ${query} has no semantic scoring`, async () => {
    const { engine, attempts } = engineWith({ bing: [record('unrelated', '1')], ddg: [record('other', '2')] });
    assert.equal(engine.assessResultQuality, undefined);
    const result = await engine.search({ query, numResults: 2 });
    assert.deepEqual(result.results.map(r => r.title), ['unrelated', 'other']);
    assert.deepEqual(attempts, ['bing', 'ddg']);
  });
}
check('URL handling validates schemes, preserves query/encoding and resolves relative paths', async () => {
  const { engine } = engineWith({ bing: [
    record('encoded', 'a%252Fb?q=1&tracking=2'),
    { ...record('bad', 'bad'), url: 'javascript:alert(1)' },
    record('distinct query', 'a%252Fb?q=2&tracking=2'),
  ] });
  const result = await engine.search({ query: 'x' });
  assert.equal(result.results.length, 2);
  assert.match(result.results[0].url, /a%252Fb\?q=1&tracking=2$/);
  assert.equal(engine.cleanBingUrl('/relative?q=%252F'), 'https://www.bing.com/relative?q=%252F');
  assert.equal(engine.cleanDuckDuckGoUrl('//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fa%252Fb'), 'https://example.org/a%2Fb');
});

// Brave internals with a fake Playwright browser: a blocked page fails at once, without retry.
function fakeBrowser(status, events) {
  const page = {
    goto: async () => { events.push('goto'); return { status: () => status }; },
    waitForSelector: async () => { events.push('wait'); throw new Error('no results selector'); },
    content: async () => { events.push('content'); return '<html></html>'; },
  };
  const context = { newPage: async () => page, close: async () => events.push('context-close') };
  return { isConnected: () => true, newContext: async () => context, close: async () => events.push('browser-close') };
}

for (const [status, expected] of [[429, 'blocked'], [403, 'blocked'], [200, 'parsed']]) {
  check(`Brave HTTP ${status} ${expected === 'blocked' ? 'fails at once without a second browser' : 'still waits for results'}`, async () => {
    configure();
    const events = [];
    const launch = playwright.chromium.launch;
    playwright.chromium.launch = async () => { events.push('launch'); return fakeBrowser(status, events); };
    try {
      const engine = new SearchEngine(new BrowserPool());
      const budget = new CallBudget(1000);
      if (expected === 'blocked') {
        await assert.rejects(engine.tryBrowserBraveSearch('alpha', 5, 1000, undefined, budget), new RegExp(`Brave returned HTTP ${status}`));
        assert.deepEqual(events, ['launch', 'goto', 'context-close']);
      } else {
        assert.deepEqual(await engine.tryBrowserBraveSearch('alpha', 5, 1000, undefined, budget), []);
        assert.deepEqual(events, ['launch', 'goto', 'wait', 'content', 'context-close']);
      }
      budget.dispose();
      await engine.closeAll();
      assert.equal(events.at(-1), 'browser-close');
    } finally {
      playwright.chromium.launch = launch;
    }
  });
}

const { formatSearchResponse } = await import(pathToFileURL(path.join(dist, 'utils.js')).href);
check('both search tools share distinguishable engine and provenance text', async () => {
  const error = new Error('HTTP 429');
  const failed = await engineWith({ bing: error, ddg: error, brave: error }).engine.search({ query: 'x' });
  const empty = await engineWith().engine.search({ query: 'x' });
  const partial = await engineWith({ bing: [record('one', '1')], ddg: error }).engine.search({ query: 'x' });
  const render = r => formatSearchResponse('x', r.results, r.engines);
  const texts = [failed, empty, partial].map(render);
  assert.equal(new Set(texts).size, 3);
  assert.match(texts[0], /All attempted engines failed/);
  assert.match(texts[1], /status=zero_parsed/);
  assert.match(texts[2], /Source engines: Browser Bing/);
  assert.match(texts[2], /Axios DuckDuckGo: attempted=true; attempts=1; parsed_count=0; status=error/);
  const { readFile } = await import('node:fs/promises');
  const source = await readFile(path.join(dist, '..', 'src', 'index.ts'), 'utf8');
  assert.equal((source.match(/const responseText = formatSearchResponse\(/g) ?? []).length, 2);
  assert.match(source, /numResults: limit/);
});

check('strict content limits, deployment precedence, booleans and Unicode', async () => {
  const { validateSearchInput, resolveContentLimit, limitContent } = await import(pathToFileURL(path.join(dist, 'utils.js')).href);
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
      assert.equal((await extractor.extractContent({ url: 'https://example.org', maxContentLength: args.maxContentLength })).content, limitContent(text, 7));
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
  const { engine, attempts } = engineWith({ bing: [record('known', 'known')] });
  engine.tryDuckDuckGoSearch = async (_q, _n, _timeout, _state, budget) => {
    attempts.push('ddg');
    return budget.wait(new Promise(() => {}));
  };
  const budget = new CallBudget(20);
  const result = await engine.search({ query: 'x', budget });
  budget.dispose();
  assert.equal(result.results[0].title, 'known');
  assert.deepEqual(attempts, ['bing', 'ddg']);
  assert.equal(result.engines.length, 3);
  assert.equal(result.engines[2].attempted, false);
  assert.match(result.engines[2].error, /deadline/);
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
