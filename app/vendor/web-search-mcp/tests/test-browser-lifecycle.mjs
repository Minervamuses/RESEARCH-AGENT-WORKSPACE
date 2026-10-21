import assert from 'node:assert/strict';
import { chromium, firefox } from 'playwright';
import { BrowserPool, CallBudget } from '../dist/browser-pool.js';
import { SearchEngine } from '../dist/search-engine.js';
import { EnhancedContentExtractor } from '../dist/enhanced-content-extractor.js';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const original = chromium.launch;
const originalFirefox = firefox.launch;
firefox.launch = async () => { throw new Error('Firefox must never launch'); };
let launches = 0, alive = 0, contextPeak = 0, closed = 0, http = 0, httpPeak = 0;
const browser = {
  isConnected: () => true,
  newContext: async () => {
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
chromium.launch = async () => { launches++; await pause(10); return browser; };
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
  assert.equal(process.getActiveResourcesInfo().filter(name => name === 'Timeout').length, 0);
  process.stdout.write('single launch, bounded contexts/HTTP, shared ownership and failed launch recovery: passed\n');
} finally {
  chromium.launch = original;
  firefox.launch = originalFirefox;
}
