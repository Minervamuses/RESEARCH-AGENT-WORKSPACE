// Offline regression for SearchEngine.search(): every exit keeps the best result found.
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
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);

const logs = [];
console.log = (...args) => logs.push(args.join(' '));
console.error = (...args) => logs.push(args.join(' '));

const record = (title, id) => ({ title, description: '', url: `https://example.org/${id}`, timestamp: 'fixed' });
const outcome = (behaviour, attempts, name) => async () => {
  attempts.push(name);
  if (behaviour instanceof Error) throw behaviour;
  return behaviour;
};

function engineWith({ bing = [], brave = [], ddg = [], handlingFails = false }) {
  const engine = new SearchEngine();
  const attempts = [];
  engine.tryBrowserBingSearch = outcome(bing, attempts, 'bing');
  engine.tryBrowserBraveSearch = outcome(brave, attempts, 'brave');
  engine.tryDuckDuckGoSearch = outcome(ddg, attempts, 'ddg');
  if (handlingFails) {
    engine.handleBrowserError = async () => { throw new Error('injected error-handling failure'); };
  }
  return { engine, attempts };
}

function configure({ quality = 'true', force = 'false' } = {}) {
  process.env.ENABLE_RELEVANCE_CHECKING = quality;
  process.env.RELEVANCE_THRESHOLD = '0.3';
  process.env.FORCE_MULTI_ENGINE_SEARCH = force;
}

const scorer = new SearchEngine();
const score = (results, query) => scorer.assessResultQuality(results, query);
const failure = () => new Error('injected engine failure');
const cases = [];
const check = (name, fn) => cases.push({ name, fn });

// Core four (engine order Bing -> DuckDuckGo -> Brave): a Chinese Bing result (the heuristic drops CJK keywords and scores it 0.5) must
// survive later engines that return nothing or fail.
const chineseQuery = '中文查詢';
const chineseBing = [record('中文相關內容', 'bing')];
for (const [name, brave, ddg] of [
  ['bing kept when brave and ddg are empty', [], []],
  ['bing kept when brave and ddg throw', failure(), failure()],
  ['bing kept when brave is empty and ddg throws', [], failure()],
]) {
  check(name, async () => {
    configure();
    assert.equal(score(chineseBing, chineseQuery), 0.5);
    const { engine, attempts } = engineWith({ bing: chineseBing, brave, ddg });
    const result = await engine.search({ query: chineseQuery });
    assert.deepEqual(result, { results: chineseBing, engine: 'Browser Bing' });
    assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
  });
}

check('a non-empty bing result scored 0 is kept', async () => {
  configure();
  const bing = [record('food hotel recipe', 'bing')];
  assert.equal(score(bing, 'alpha'), 0, 'fixture must cover a zero-scored non-empty result');
  const { engine } = engineWith({ bing, brave: failure() });
  assert.deepEqual(await engine.search({ query: 'alpha' }), { results: bing, engine: 'Browser Bing' });
});

check('higher bing beats a lower brave that meets the threshold', async () => {
  configure();
  const query = 'alpha beta gamma';
  const bing = [record('alpha gamma', 'bing')];
  const brave = [record('beta', 'brave')];
  const bingScore = score(bing, query);
  const braveScore = score(brave, query);
  assert.ok(bingScore > braveScore && bingScore < 0.8 && braveScore >= 0.3, `${bingScore} ${braveScore}`);
  const { engine, attempts } = engineWith({ bing, brave });
  assert.deepEqual(await engine.search({ query }), { results: bing, engine: 'Browser Bing' });
  assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
});

check('a later, truly better result replaces bing with its own engine name', async () => {
  configure();
  const query = 'alpha beta gamma';
  const bing = [record('beta', 'bing')];
  const brave = [record('alpha beta gamma', 'brave')];
  assert.ok(score(brave, query) > score(bing, query));
  const { engine } = engineWith({ bing, brave });
  assert.deepEqual(await engine.search({ query }), { results: brave, engine: 'Browser Brave' });
});

check('equal scores keep the earlier engine', async () => {
  configure();
  const query = 'alpha beta gamma';
  const bing = [record('beta', 'bing')];
  const ddg = [record('beta', 'ddg')];
  assert.equal(score(bing, query), score(ddg, query));
  const { engine } = engineWith({ bing, ddg });
  assert.deepEqual(await engine.search({ query }), { results: bing, engine: 'Browser Bing' });
});

check('all engines empty still return the empty contract', async () => {
  configure();
  const { engine, attempts } = engineWith({});
  assert.deepEqual(await engine.search({ query: 'alpha' }), { results: [], engine: 'None' });
  assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
});

check('all engines failing still return the empty contract', async () => {
  configure();
  const { engine } = engineWith({ bing: failure(), brave: failure(), ddg: failure() });
  assert.deepEqual(await engine.search({ query: 'alpha' }), { results: [], engine: 'None' });
});

check('failed error handling keeps an earlier best result', async () => {
  configure();
  const { engine, attempts } = engineWith({ bing: chineseBing, ddg: failure(), handlingFails: true });
  assert.deepEqual(await engine.search({ query: chineseQuery }), { results: chineseBing, engine: 'Browser Bing' });
  assert.deepEqual(attempts, ['bing', 'ddg']);
});

check('failed error handling without a result keeps the failure contract', async () => {
  configure();
  const { engine } = engineWith({ bing: failure(), handlingFails: true });
  await assert.rejects(engine.search({ query: 'alpha' }), /Failed to perform search: injected error-handling failure/);
});

check('forced multi-engine search keeps bing when later engines add nothing', async () => {
  configure({ force: 'true' });
  const query = 'alpha beta gamma';
  const bing = [record('alpha beta gamma', 'bing')];
  const { engine, attempts } = engineWith({ bing, brave: [record('beta', 'brave')], ddg: failure() });
  assert.deepEqual(await engine.search({ query }), { results: bing, engine: 'Browser Bing' });
  assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
});

check('a usable DuckDuckGo result is returned before the slower Brave browser runs', async () => {
  configure();
  const query = 'alpha beta gamma';
  const ddg = [record('alpha beta gamma', 'ddg')];
  const { engine, attempts } = engineWith({ bing: [record('zzz', 'bing')], ddg, brave: [record('alpha beta gamma', 'brave')] });
  assert.deepEqual(await engine.search({ query }), { results: ddg, engine: 'Axios DuckDuckGo' });
  assert.deepEqual(attempts, ['bing', 'ddg']);
});

check('Brave still runs when DuckDuckGo has nothing usable', async () => {
  configure();
  const query = 'alpha beta gamma';
  const brave = [record('alpha beta gamma', 'brave')];
  const { engine, attempts } = engineWith({ bing: [record('zzz', 'bing')], ddg: failure(), brave });
  assert.deepEqual(await engine.search({ query }), { results: brave, engine: 'Browser Brave' });
  assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
});

check('disabled quality checking returns the first non-empty engine', async () => {
  configure({ quality: 'false' });
  const { engine, attempts } = engineWith({ bing: chineseBing, brave: [record('other', 'brave')] });
  assert.deepEqual(await engine.search({ query: chineseQuery }), { results: chineseBing, engine: 'Browser Bing' });
  assert.deepEqual(attempts, ['bing']);
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
    const launch = playwright.firefox.launch;
    playwright.firefox.launch = async () => { events.push('launch'); return fakeBrowser(status, events); };
    try {
      const engine = new SearchEngine();
      if (expected === 'blocked') {
        await assert.rejects(engine.tryBrowserBraveSearch('alpha', 5, 1000), new RegExp(`Brave returned HTTP ${status}`));
        assert.deepEqual(events, ['launch', 'goto', 'context-close', 'browser-close']);
      } else {
        assert.deepEqual(await engine.tryBrowserBraveSearch('alpha', 5, 1000), []);
        assert.deepEqual(events, ['launch', 'goto', 'wait', 'content', 'context-close', 'browser-close']);
      }
    } finally {
      playwright.firefox.launch = launch;
    }
  });
}

check('a blocked Brave fallback keeps the earlier Bing result', async () => {
  configure();
  const query = 'alpha beta gamma';
  const bing = [record('alpha', 'bing')];
  const { engine, attempts } = engineWith({ bing, ddg: [], brave: Object.assign(new Error('Brave returned HTTP 429'), { braveBlocked: true }) });
  assert.deepEqual(await engine.search({ query }), { results: bing, engine: 'Browser Bing' });
  assert.deepEqual(attempts, ['bing', 'ddg', 'brave']);
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
