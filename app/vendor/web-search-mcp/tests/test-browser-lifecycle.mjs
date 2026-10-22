import assert from 'node:assert/strict';
import { chromium, firefox } from 'playwright';
import { BrowserPool, CallBudget, OPERATION_TIMEOUTS } from '../dist/browser-pool.js';
import { SearchEngine } from '../dist/search-engine.js';
import { EnhancedContentExtractor } from '../dist/enhanced-content-extractor.js';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const waitUntil = async (check, ms = 2000) => {
  const end = performance.now() + ms;
  while (!check()) {
    if (performance.now() > end) throw new Error('condition not reached');
    await pause(5);
  }
};
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
    const reader = new EnhancedContentExtractor({ withHttp: fn => fn(), withPage: (fn, b, onStart) => { onStart?.(); return b.wait(fn(page)); } });
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
    assert.match(formatPageRead(capped.read), /- browser: status=200; read_status=empty_text; .*render_wait_ms=\d+; .*error=No visible text after waiting \d+ ms for client rendering \(limit 120 ms\)/);
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

  // FA05/FA06: operation caps are total caps, page windows start at the first read slot.
  const savedCaps = { ...OPERATION_TIMEOUTS };
  try {
    OPERATION_TIMEOUTS.pageRequest = 600;
    const dripServer = createServer((_request, response) => {
      response.writeHead(200, { 'content-type': 'text/html' });
      const drip = setInterval(() => response.write('a'), 100);
      response.on('close', () => clearInterval(drip));
    });
    await new Promise(resolve => dripServer.listen(0, '127.0.0.1', resolve));
    try {
      const dripPool = new BrowserPool();
      const dripReader = new EnhancedContentExtractor(dripPool);
      let dripFallback = 0, slotsMid;
      dripReader.extractWithBrowser = async (_options, _state, started) => { started(); dripFallback++; return ''; };
      setTimeout(() => { slotsMid = dripPool.http.activeCount; }, 300);
      const dripBudget = new CallBudget(5000);
      const begin = performance.now();
      const dripRead = await dripReader.extractContent({ url: `http://127.0.0.1:${dripServer.address().port}/drip`, budget: dripBudget });
      const dripMs = performance.now() - begin;
      dripBudget.dispose();
      assert.ok(dripMs >= 550 && dripMs < 1500, `slow drip ended after ${dripMs} ms`);
      assert.match(dripRead.attempts[0].error, /^HTTP page read exceeded its 600 ms operation limit$/);
      assert.equal(slotsMid, 1);
      assert.equal(dripPool.http.activeCount, 0);
      assert.equal(dripFallback, 1);
      assert.deepEqual(dripRead.attempts.map(a => a.transport), ['http', 'browser']);
    } finally {
      dripServer.closeAllConnections();
      await new Promise(resolve => dripServer.close(resolve));
    }

    OPERATION_TIMEOUTS.pageRead = 80;
    const never = () => new Promise(() => undefined);
    let stuckCloses = 0;
    const stuckPool = page => {
      chromium.launch = async () => ({
        isConnected: () => true, version: () => '777.0.0.0',
        newContext: async () => ({ newPage: async () => page, close: async () => { stuckCloses++; } }),
        close: async () => undefined,
      });
      return new BrowserPool();
    };
    const stuckPage = (media, overrides) => ({
      on: () => undefined, off: () => undefined, mainFrame: () => undefined,
      goto: async () => ({ status: () => 200, headers: () => ({ 'content-type': media }) }),
      url: () => 'https://www.google.com/search?q=x', evaluate: async () => 'text', waitForLoadState: async () => undefined,
      waitForSelector: async () => undefined, title: async () => 'T', content: async () => '<p>x</p>',
      locator: () => ({ innerText: async () => 'plain' }), ...overrides,
    });
    for (const [media, overrides, what] of [
      ['text/html', { title: never }, 'page.title()'],
      ['text/html', { content: never }, 'page.content()'],
      ['text/plain', { locator: () => ({ innerText: never }) }, 'body innerText'],
    ]) {
      const pool = stuckPool(stuckPage(media, overrides));
      const reader = new EnhancedContentExtractor(pool);
      reader.extractWithAxios = async (_options, state) => { state.httpStatus = 200; state.contentType = media; return ''; };
      const before = stuckCloses, budget = new CallBudget(5000), begin = performance.now();
      const read = await reader.extractContent({ url: 'https://example.org/stuck', budget });
      budget.dispose();
      assert.ok(performance.now() - begin < 1000, what);
      assert.equal(read.status, 'timeout', what);
      assert.equal(read.attempts[1].error, `${what} exceeded its 80 ms page read limit`);
      assert.equal(stuckCloses, before + 1, `${what}: context closed`);
      await pool.closeAll();
    }
    for (const [method, name] of [['tryGoogleSearch', 'Google'], ['tryBingSearch', 'Bing']]) {
      const pool = stuckPool(stuckPage('text/html', { content: never }));
      const before = stuckCloses, budget = new CallBudget(5000), begin = performance.now();
      await assert.rejects(new SearchEngine(pool)[method]('x', 5, 1000, undefined, budget), new RegExp(`^Error: ${name} results page\\.content\\(\\) exceeded its 80 ms page read limit$`));
      budget.dispose();
      assert.ok(performance.now() - begin < 1000, name);
      assert.equal(stuckCloses, before + 1, `${name}: context closed`);
      await pool.closeAll();
    }

    OPERATION_TIMEOUTS.pageTotal = 400;
    const windowReader = new EnhancedContentExtractor(new BrowserPool());
    windowReader.extractWithAxios = async options => { await options.budget.wait(pause(200)); return 'read in time'; };
    const ten = Array.from({ length: 10 }, (_v, i) => ({ title: `p${i}`, url: `https://example.org/${i}`, description: '' }));
    const windowBudget = new CallBudget(5000);
    const windowed = await windowReader.extractContentForResults(ten, 10, undefined, windowBudget);
    windowBudget.dispose();
    assert.deepEqual(windowed.map(r => r.read.status), Array(10).fill('text'));
    const slowReader = new EnhancedContentExtractor(new BrowserPool());
    slowReader.extractWithAxios = async options => { await options.budget.wait(pause(250)); return ''; };
    slowReader.extractWithBrowser = async (options, _state, started) => { started(); await options.budget.wait(pause(250)); return 'too late'; };
    const slowBudget = new CallBudget(5000);
    const [overWindow] = await slowReader.extractContentForResults([ten[0]], 1, undefined, slowBudget);
    slowBudget.dispose();
    assert.equal(overWindow.read.status, 'timeout');
    assert.equal(overWindow.read.error, 'page read window exceeded (400 ms)');
    assert.deepEqual(overWindow.read.attempts.map(a => [a.transport, a.error ?? null]), [['http', null], ['browser', 'page read window exceeded (400 ms)']]);
  } finally {
    Object.assign(OPERATION_TIMEOUTS, savedCaps);
    chromium.launch = original;
  }
  await pause(120);

  // Old P4-S2 focus cases: hung navigation ends at its operation cap, queued pages expire, aborts close sockets.
  {
    const saved = { ...OPERATION_TIMEOUTS };
    const { getEventListeners } = await import('node:events');
    const hangs = (_target, options) => options?.timeout
      ? new Promise((_resolve, reject) => setTimeout(() => reject(Object.assign(new Error(`Timeout ${options.timeout}ms exceeded.`), { name: 'TimeoutError' })), options.timeout))
      : new Promise(() => undefined);
    const okResponse = { status: () => 200, headers: () => ({ 'content-type': 'text/html' }) };
    const hungPage = overrides => ({
      on: () => undefined, off: () => undefined, mainFrame: () => undefined, url: () => 'https://www.google.com/search?q=x',
      goto: async () => okResponse, waitForSelector: async () => undefined, content: async () => '<html></html>',
      title: async () => '', evaluate: async () => 'text', waitForLoadState: async () => undefined, ...overrides,
    });
    const leasePool = page => ({ withPage: (fn, budget, onStart) => { onStart?.(); return budget.wait(fn(page)); }, withHttp: fn => fn() });
    const elapsed = async fn => { const begin = performance.now(); await fn(); return performance.now() - begin; };
    try {
      Object.assign(OPERATION_TIMEOUTS, { pageRequest: 50, searchRequest: 50, searchSelector: 50, linkResolve: 50 });
      // Page read navigation (N16c).
      const navReader = new EnhancedContentExtractor(leasePool(hungPage({ goto: hangs })));
      navReader.extractWithAxios = async () => '';
      let read;
      const navMs = await elapsed(async () => { const b = new CallBudget(2000); read = await navReader.extractContent({ url: 'https://example.org/hung', budget: b }); b.dispose(); });
      assert.ok(navMs < 500, `page goto ended after ${navMs} ms`);
      assert.equal(read.status, 'timeout');
      assert.match(read.attempts[1].error, /Timeout 50ms exceeded/);
      // Google and Bing: a hung goto, and a hung result wait that still lets the engine finish.
      for (const method of ['tryGoogleSearch', 'tryBingSearch']) {
        const gotoEngine = new SearchEngine(leasePool(hungPage({ goto: hangs })));
        let gotoMs = await elapsed(async () => { const b = new CallBudget(2000); await assert.rejects(gotoEngine[method]('x', 5, b.timeout(OPERATION_TIMEOUTS.searchRequest), undefined, b), /Timeout 50ms/); b.dispose(); });
        assert.ok(gotoMs < 500, `${method} goto ended after ${gotoMs} ms`);
        const waitEngine = new SearchEngine(leasePool(hungPage({ waitForSelector: hangs })));
        gotoMs = await elapsed(async () => { const b = new CallBudget(2000); assert.deepEqual(await waitEngine[method]('x', 5, 50, undefined, b), []); b.dispose(); });
        assert.ok(gotoMs < 500, `${method} result wait ended after ${gotoMs} ms`);
      }
      // Engine redirect resolution navigation.
      const wrapperPage = hungPage({
        goto: async (target, options) => target.includes('/goto') ? hangs(target, options) : okResponse,
        content: async () => '<div id="search"><a href="/goto?u=1"><h3>Wrapped</h3></a></div>',
      });
      const resolver = new SearchEngine(leasePool(wrapperPage));
      resolver.tryBingSearch = async () => [];
      let resolved;
      const resolveMs = await elapsed(async () => { const b = new CallBudget(2000); resolved = await resolver.search({ query: 'x', numResults: 1, budget: b }); b.dispose(); });
      assert.ok(resolveMs < 500, `link resolution ended after ${resolveMs} ms`);
      assert.equal(resolved.results[0].resolution.outcome, 'timeout');
      Object.assign(OPERATION_TIMEOUTS, saved);

      // A queued page lease expires at its deadline and never opens a page (N09g).
      const previousPages = process.env.MAX_CONCURRENT_PAGES;
      process.env.MAX_CONCURRENT_PAGES = '1';
      let pagesOpened = 0;
      chromium.launch = async () => ({ ...browser, newContext: async () => ({ newPage: async () => { pagesOpened++; return {}; }, close: async () => undefined }) });
      const onePage = new BrowserPool();
      if (previousPages === undefined) delete process.env.MAX_CONCURRENT_PAGES; else process.env.MAX_CONCURRENT_PAGES = previousPages;
      let releasePage;
      const holding = onePage.withPage(() => new Promise(resolve => { releasePage = resolve; }));
      await waitUntil(() => pagesOpened === 1);
      const queueBudget = new CallBudget(50);
      let ranLate = false;
      const queueMs = await elapsed(() => assert.rejects(onePage.withPage(async () => { ranLate = true; }, queueBudget), /deadline/));
      queueBudget.dispose();
      assert.ok(queueMs < 300, `queued page expired after ${queueMs} ms`);
      releasePage();
      await holding;
      await pause(10);
      assert.equal(ranLate, false);
      assert.equal(pagesOpened, 1);
      assert.deepEqual([onePage.pages.activeCount, onePage.pages.pendingCount], [0, 0]);
      await onePage.closeAll();
      chromium.launch = original;

      // An explicit abort closes an in-flight HTTP read long before any deadline (N26).
      const sockets = [];
      const stalled = createServer(request => { const entry = { closed: undefined }; sockets.push(entry); request.socket.once('close', () => { entry.closed = performance.now(); }); });
      await new Promise(resolve => stalled.listen(0, '127.0.0.1', resolve));
      try {
        const abortPool = new BrowserPool();
        const abortReader = new EnhancedContentExtractor(abortPool);
        abortReader.extractWithBrowser = async () => { throw new Error('no fallback after an explicit abort'); };
        const abortBudget = new CallBudget(5000);
        const pending = abortReader.extractContent({ url: `http://127.0.0.1:${stalled.address().port}/stalled`, budget: abortBudget });
        await waitUntil(() => sockets.length === 1);
        const abortedAt = performance.now();
        abortBudget.abort();
        const abortedRead = await pending;
        abortBudget.dispose();
        await waitUntil(() => sockets[0].closed !== undefined, 1000);
        assert.ok(sockets[0].closed - abortedAt < 250, `socket closed ${sockets[0].closed - abortedAt} ms after abort`);
        assert.equal(abortedRead.status, 'cancelled');
        assert.deepEqual([abortPool.http.activeCount, abortPool.http.pendingCount, abortPool.pages.activeCount], [0, 0, 0]);
      } finally {
        stalled.closeAllConnections();
        await new Promise(resolve => stalled.close(resolve));
      }

      // A disposed child budget leaves no abort listener on its parent (N09b).
      const parent = new CallBudget(1000);
      const listeners = getEventListeners(parent.signal, 'abort').length;
      const childBudget = parent.child(100);
      assert.equal(getEventListeners(parent.signal, 'abort').length, listeners + 1);
      childBudget.dispose();
      assert.equal(getEventListeners(parent.signal, 'abort').length, listeners);
      parent.dispose();
    } finally {
      Object.assign(OPERATION_TIMEOUTS, saved);
      chromium.launch = original;
    }
  }

  // FA07: withPage reports a start once its slot is held, before launch; a queued lease never does.
  {
    let starts = 0, failing = true;
    chromium.launch = async () => { if (failing) throw new Error('launch failed before any page'); return browser; };
    const startPool = new BrowserPool();
    const launchBudget = new CallBudget(1000);
    await assert.rejects(startPool.withPage(async () => 'never', launchBudget, () => { starts++; }), /launch failed/);
    launchBudget.dispose();
    assert.equal(starts, 1, 'a failed launch still started');
    failing = false;
    let release;
    const holding = new Promise(resolve => { release = resolve; });
    const busy = [startPool.withPage(() => holding), startPool.withPage(() => holding)];
    const queuedBudget = new CallBudget(30);
    let queuedStarts = 0;
    await assert.rejects(startPool.withPage(async () => 'late', queuedBudget, () => { queuedStarts++; }), /deadline/);
    queuedBudget.dispose();
    release();
    await Promise.all(busy);
    await pause(5);
    assert.equal(queuedStarts, 0, 'a lease that expired in the queue never started');
    await startPool.closeAll();
    chromium.launch = original;
  }

  // FA10: owned Chromium is recognised after argv/comm rewrites; a stuck close still ends with SIGKILL.
  {
    const { spawn } = await import('node:child_process');
    const { readFileSync } = await import('node:fs');
    const flag = `--web-search-owner=${process.pid}`;
    const children = [];
    const startChild = title => {
      const child = spawn(process.execPath, ['-e', `process.title = ${JSON.stringify(title)}; setInterval(() => {}, 1000);`], { detached: true, stdio: 'ignore' });
      children.push(child);
      return child;
    };
    const exited = child => new Promise(resolve => { if (child.exitCode !== null || child.signalCode) resolve(); else child.once('exit', resolve); });
    const within = (promise, ms, late) => {
      let timer;
      return Promise.race([promise, new Promise(resolve => { timer = setTimeout(() => resolve(late), ms); })]).finally(() => clearTimeout(timer));
    };
    const statFields = pid => { const text = readFileSync(`/proc/${pid}/stat`, 'utf8'); return text.slice(text.lastIndexOf(')') + 1).trim().split(/\s+/); };
    const cleanupCap = OPERATION_TIMEOUTS.cleanup;
    try {
      const owned = startChild(`a) b c d ${flag}`);
      const plain = startChild('a) b c d unrelated');
      const forged = startChild(`a) b c d ${flag}`);
      for (const child of children) {
        for (let i = 0; i < 100 && !readFileSync(`/proc/${child.pid}/cmdline`, 'utf8').startsWith('a) b c d'); i++) await pause(10);
      }
      // Scenario check: cmdline is one space-joined string and comm contains ") ".
      assert.equal(readFileSync(`/proc/${owned.pid}/cmdline`, 'utf8').split('\0').filter(Boolean).length, 1);
      assert.equal(readFileSync(`/proc/${owned.pid}/comm`, 'utf8').trim(), 'a) b c d --web-');
      OPERATION_TIMEOUTS.cleanup = 100;
      let closes = 0;
      chromium.launch = async () => ({
        isConnected: () => true, version: () => '777.0.0.0', newContext: async () => ({}),
        close: () => { closes++; return new Promise(() => undefined); },
      });
      const ownerPool = new BrowserPool();
      await ownerPool.getBrowser();
      assert.ok(ownerPool.owned.has(owned.pid), 'rewritten owner process recognised');
      assert.ok(!ownerPool.owned.has(plain.pid), 'process without the flag is not owned');
      // A recorded identity whose start time no longer matches is never killed.
      const checker = new BrowserPool();
      checker.owned.set(forged.pid, `${statFields(forged.pid)[19]}0`);
      checker.killOwnedBrowsers();
      await pause(50);
      assert.equal(forged.signalCode, null, 'start time mismatch must not be killed');
      const begin = performance.now();
      const outcome = await within(ownerPool.closeAll().then(() => 'closed'), 2000, 'hung');
      assert.equal(outcome, 'closed');
      assert.ok(performance.now() - begin < 1000, `bounded close took ${performance.now() - begin} ms`);
      assert.equal(closes, 1);
      await within(Promise.all([exited(owned), exited(forged)]), 1000);
      // closeAll re-reads identities, so both flagged processes of this pool are owned groups.
      assert.equal(owned.signalCode, 'SIGKILL');
      assert.equal(forged.signalCode, 'SIGKILL');
      await pause(50);
      assert.equal(plain.exitCode, null);
      assert.equal(plain.signalCode, null);
    } finally {
      OPERATION_TIMEOUTS.cleanup = cleanupCap;
      chromium.launch = original;
      for (const child of children) {
        if (child.exitCode === null && !child.signalCode) { try { process.kill(-child.pid, 'SIGKILL'); } catch { /* exited */ } }
      }
      await Promise.all(children.map(exited));
    }
  }

  assert.equal(process.getActiveResourcesInfo().filter(name => name === 'Timeout').length, 0);
  process.stdout.write('single launch, bounded contexts/HTTP, shared ownership and failed launch recovery: passed\n');
} finally {
  chromium.launch = original;
  firefox.launch = originalFirefox;
}
