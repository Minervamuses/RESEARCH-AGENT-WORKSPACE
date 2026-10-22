import assert from 'node:assert/strict';
import { chromium, firefox } from 'playwright';
import { BrowserPool, CallBudget, OPERATION_TIMEOUTS } from '../dist/browser-pool.js';
import { SearchEngine } from '../dist/search-engine.js';
import { EnhancedContentExtractor } from '../dist/enhanced-content-extractor.js';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const original = chromium.launch;
const originalFirefox = firefox.launch;
firefox.launch = async () => { throw new Error('Firefox must never launch'); };
let launches = 0, alive = 0, contextPeak = 0, closed = 0, http = 0, httpPeak = 0;
const launchOptions = [], contextOptions = [];
const browser = {
  isConnected: () => true,
  version: () => '777.0.0.0',
  newContext: async options => {
    contextOptions.push(options);
    alive++;
    contextPeak = Math.max(contextPeak, alive);
    let released = false;
    return {
      newPage: async () => ({}),
      close: async () => { if (!released) { alive--; released = true; } },
    };
  },
  close: async () => { assert.equal(alive, 0); closed++; },
};
chromium.launch = async options => { launchOptions.push(options); launches++; await pause(10); return browser; };
try {
  const pool = new BrowserPool();
  const both = await Promise.all([pool.getBrowser(), pool.getBrowser(), pool.getBrowser()]);
  assert.equal(launches, 1);
  assert.ok(both.every(item => item === browser));
  await Promise.all(Array.from({ length: 7 }, () => pool.withPage(async () => {
    assert.equal(closed, 0);
    await pause(5);
  })));
  assert.equal(contextPeak, 2);
  assert.equal(alive, 0);
  // FU02/FU03: full Chromium (new headless) and a normal UA from the actual browser version.
  assert.equal(launchOptions[0].channel, 'chromium');
  assert.equal(contextOptions.length, 7);
  for (const options of contextOptions) {
    assert.match(options.userAgent, /^Mozilla\/5\.0 \(X11; Linux x86_64\) AppleWebKit\/537\.36 \(KHTML, like Gecko\) Chrome\/777\.0\.0\.0 Safari\/537\.36$/);
    assert.doesNotMatch(options.userAgent, /Headless/);
  }
  await Promise.all(Array.from({ length: 7 }, () => pool.withHttp(async () => {
    http++; httpPeak = Math.max(httpPeak, http); await pause(5); http--;
  })));
  assert.equal(httpPeak, 2);
  assert.equal(new SearchEngine().browserPool, new EnhancedContentExtractor().browserPool);
  await pool.closeAll();
  assert.equal(closed, 1);
  let failed = true;
  chromium.launch = async () => { if (failed) { failed = false; throw new Error('launch failure'); } return browser; };
  const retryPool = new BrowserPool();
  await assert.rejects(retryPool.getBrowser(), /launch failure/);
  assert.equal(await retryPool.getBrowser(), browser);
  await retryPool.closeAll();

  // Queue expiry cannot turn into a later navigation.
  const queuedPool = new BrowserPool();
  let release;
  const held = new Promise(resolve => { release = resolve; });
  const occupied = [queuedPool.withHttp(() => held), queuedPool.withHttp(() => held)];
  const short = new CallBudget(15);
  let lateRequests = 0;
  await assert.rejects(queuedPool.withHttp(async () => { lateRequests++; }, short), /deadline/);
  short.dispose();
  release();
  await Promise.all(occupied);
  await pause(5);
  assert.equal(lateRequests, 0);
  // An uncancellable launch finishing after the last caller aborted is closed.
  const latePool = new BrowserPool();
  const launchBudget = new CallBudget(10);
  let lateClosed = 0;
  chromium.launch = async () => { await pause(30); return { ...browser, close: async () => { lateClosed++; } }; };
  await assert.rejects(latePool.getBrowser(launchBudget), /deadline/);
  launchBudget.dispose();
  await pause(40);
  assert.equal(lateClosed, 1);
  const cancelled = new CallBudget(1000);
  cancelled.abort();
  await assert.rejects(queuedPool.withPage(async () => { lateRequests++; }, cancelled), /cancelled/);
  cancelled.dispose();
  assert.equal(lateRequests, 0);

  // Google's result wait is bounded by searchSelector; the next engine still has budget.
  const selectorCap = OPERATION_TIMEOUTS.searchSelector;
  OPERATION_TIMEOUTS.searchSelector = 20;
  const selectorEvents = [];
  const selectorPage = {
    goto: async (_url, options) => { assert.ok(options.timeout <= 4000); return { status: () => 200 }; },
    waitForSelector: async (_selector, options) => {
      selectorEvents.push(options.timeout);
      await pause(options.timeout);
      throw Object.assign(new Error('selector timeout'), { name: 'TimeoutError' });
    },
    content: async () => '<html></html>',
    url: () => 'https://www.google.com/search?q=x',
  };
  const selectorEngine = new SearchEngine({ withPage: (fn, _budget) => fn(selectorPage) });
  selectorEngine.tryBingSearch = async (_query, _n, _timeout, _state, budget, admit) => {
    assert.ok(budget.remaining() > 100);
    const batch = [{ title: 'next engine', url: 'https://example.org', description: '' }];
    await admit(batch, { url: () => 'https://www.bing.com/search' });
    return batch;
  };
  const selectorBudget = new CallBudget(300);
  const selectorResult = await selectorEngine.search({ query: 'x', numResults: 1, budget: selectorBudget });
  selectorBudget.dispose();
  OPERATION_TIMEOUTS.searchSelector = selectorCap;
  assert.equal(selectorResult.results[0].title, 'next engine');
  assert.deepEqual(selectorEvents, [20]);
  const { createServer } = await import('node:http');
  let received = 0, socketClosed = 0, fallback = 0;
  const server = createServer((request, _response) => {
    received++;
    request.socket.once('close', () => { socketClosed++; });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const reader = new EnhancedContentExtractor(new BrowserPool());
    reader.extractWithBrowser = async () => { fallback++; return ''; };
    const httpBudget = new CallBudget(35);
    const read = await reader.extractContent({ url: `http://127.0.0.1:${server.address().port}/slow`, budget: httpBudget });
    httpBudget.dispose();
    await pause(20);
    assert.equal(read.status, 'timeout');
    assert.equal(read.attempts.length, 1);
    assert.equal(received, 1);
    assert.equal(socketClosed, 1);
    assert.equal(fallback, 0);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }

  let closeFailures = 0;
  chromium.launch = async () => ({
    isConnected: () => true,
    version: () => '777.0.0.0',
    newContext: async () => ({
      newPage: async () => ({}),
      close: async () => { throw new Error('injected context close failure'); },
    }),
    close: async () => { closeFailures++; throw new Error('injected browser close failure'); },
  });
  const brokenPool = new BrowserPool();
  assert.equal(await brokenPool.withPage(async () => 'known result'), 'known result');
  await Promise.all([brokenPool.closeAll(), brokenPool.closeAll()]);
  assert.equal(closeFailures, 1);
  let pendingClosed = 0;
  chromium.launch = async () => { await pause(30); return { ...browser, close: async () => { pendingClosed++; } }; };
  const closingPool = new BrowserPool();
  const pendingBudget = new CallBudget(10);
  const pendingLaunch = closingPool.getBrowser(pendingBudget);
  await pause(5);
  const closingLaunch = closingPool.closeAll();
  await assert.rejects(pendingLaunch, /deadline/);
  await closingLaunch;
  pendingBudget.dispose();
  assert.equal(pendingClosed, 1);

  const oldPages = process.env.MAX_CONCURRENT_PAGES, oldHttp = process.env.MAX_CONCURRENT_HTTP;
  try {
    process.env.MAX_CONCURRENT_PAGES = '1';
    process.env.MAX_CONCURRENT_HTTP = '1';
    const configuredPool = new BrowserPool();
    let runningHttp = 0, configuredPeak = 0;
    await Promise.all(Array.from({ length: 3 }, () => configuredPool.withHttp(async () => {
      runningHttp++; configuredPeak = Math.max(configuredPeak, runningHttp); await pause(5); runningHttp--;
    })));
    assert.equal(configuredPeak, 1);
    process.env.MAX_CONCURRENT_PAGES = '0';
    assert.throws(() => new BrowserPool(), /MAX_CONCURRENT_PAGES/);
    process.env.MAX_CONCURRENT_PAGES = '1';
    process.env.MAX_CONCURRENT_HTTP = '1junk';
    assert.throws(() => new BrowserPool(), /MAX_CONCURRENT_HTTP/);
  } finally {
    if (oldPages === undefined) delete process.env.MAX_CONCURRENT_PAGES; else process.env.MAX_CONCURRENT_PAGES = oldPages;
    if (oldHttp === undefined) delete process.env.MAX_CONCURRENT_HTTP; else process.env.MAX_CONCURRENT_HTTP = oldHttp;
  }
  // The client-render wait is bounded by min(renderSettle, remaining budget) and ends on cancellation.
  const renderCap = OPERATION_TIMEOUTS.renderSettle;
  const { formatPageRead } = await import('../dist/utils.js');
  const settleTimeouts = [];
  const renderPage = (overrides = {}) => ({
    goto: async () => ({ status: () => 200, headers: () => ({ 'content-type': 'text/html' }) }),
    url: () => 'https://example.org/app', title: async () => 'App', content: async () => '<html><body></body></html>',
    on: () => undefined, off: () => undefined, mainFrame: () => undefined,
    evaluate: async () => '',
    waitForLoadState: (_state, options) => { settleTimeouts.push(options.timeout); return new Promise(() => undefined); },
    ...overrides,
  });
  const renderRead = async (page, budget) => {
    const reader = new EnhancedContentExtractor({ withHttp: fn => fn(), withPage: (fn, b) => b.wait(fn(page)) });
    reader.extractWithAxios = async (_options, state) => { state.httpStatus = 200; state.contentType = 'text/html'; return ''; };
    const begin = performance.now();
    try { return { read: await reader.extractContent({ url: 'https://example.org/app', budget }), ms: performance.now() - begin }; }
    finally { budget.dispose(); }
  };
  try {
    OPERATION_TIMEOUTS.renderSettle = 120;
    const capped = await renderRead(renderPage(), new CallBudget(5000));
    assert.equal(capped.read.status, 'empty_text');
    assert.equal(settleTimeouts.at(-1), 120);
    assert.ok(capped.ms >= 100 && capped.ms < 1000, `render wait ${capped.ms}`);
    assert.match(formatPageRead(capped.read), /- browser: status=200; error=No visible text after waiting \d+ ms for client rendering \(limit 120 ms\)/);
    OPERATION_TIMEOUTS.renderSettle = 5000;
    const short = await renderRead(renderPage(), new CallBudget(200));
    assert.ok(settleTimeouts.at(-1) <= 200, `render wait limited by budget: ${settleTimeouts.at(-1)}`);
    assert.ok(short.ms < 1000, `budget-bound render wait ${short.ms}`);
    // The capped wait ends at the call deadline, so the read either just completes or times out.
    assert.ok(['empty_text', 'timeout'].includes(short.read.status), short.read.status);
    const cancelBudget = new CallBudget(5000);
    setTimeout(() => cancelBudget.abort(), 50);
    const cancelledRead = await renderRead(renderPage(), cancelBudget);
    assert.ok(cancelledRead.ms < 1000, `cancelled render wait ${cancelledRead.ms}`);
    assert.equal(cancelledRead.read.status, 'cancelled');
    let polls = 0;
    const ready = await renderRead(renderPage({
      evaluate: async () => (++polls >= 2 ? 'Rendered' : ''),
      waitForLoadState: async () => undefined,
      content: async () => '<html><body><p>Rendered</p></body></html>',
    }), new CallBudget(5000));
    assert.equal(ready.read.status, 'text');
    assert.equal(ready.read.content, 'Rendered');
    assert.ok(ready.ms < 1000, `settled render wait ${ready.ms}`);
    await pause(120);
  } finally { OPERATION_TIMEOUTS.renderSettle = renderCap; }

  assert.equal(process.getActiveResourcesInfo().filter(name => name === 'Timeout').length, 0);
  process.stdout.write('single launch, bounded contexts/HTTP, shared ownership and failed launch recovery: passed\n');
} finally {
  chromium.launch = original;
  firefox.launch = originalFirefox;
}
