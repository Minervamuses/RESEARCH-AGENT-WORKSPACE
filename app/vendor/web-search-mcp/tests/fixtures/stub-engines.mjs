// Test-only preload for dist/index.js: node --import ./tests/fixtures/stub-engines.mjs <dist>/index.js
// Configuration comes only from these test variables; none of them is a product setting:
//   STUB_LOG             JSON-lines file for recorded events (required)
//   STUB_PAGE_BASE       base URL of the test's local HTTP server for stub candidates
//   STUB_CLOSEALL_DELAY  milliseconds closeAll waits before closing the pool
//   STUB_FAKE_BROWSER    "1": chromium.launch returns a fake browser instead of failing
import { appendFileSync } from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

const dist = path.dirname(path.resolve(process.argv[1]));
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
const { BrowserPool, CallBudget } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const record = (event, fields = {}) => appendFileSync(process.env.STUB_LOG, `${JSON.stringify({ event, at: Date.now(), ...fields })}\n`);

// Only loopback connections: the entry test never needs the public network.
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const options = typeof args[0] === 'object' && args[0] !== null ? args[0] : { host: typeof args[1] === 'string' ? args[1] : undefined };
  const host = options.host ?? options.hostname ?? 'localhost';
  if (!options.path && !['127.0.0.1', 'localhost', '::1'].includes(host)) throw new Error(`stub: non-loopback connection to ${host}`);
  return connect.apply(this, args);
};

// The engine returns fixed direct candidates, so no wrapper navigation happens.
const base = process.env.STUB_PAGE_BASE ?? 'http://127.0.0.1:9';
SearchEngine.prototype.tryGoogleSearch = async function (query, numResults, _timeout, state, _budget, admit) {
  record('engine', { name: 'Google', query, numResults });
  state.attempted = true;
  state.attempts++;
  const batch = [1, 2, 3, 4].map(id => ({ title: `Stub ${id}`, url: `${base}/page/${id}`, description: `stub snippet ${id}` }));
  await admit(batch, { url: () => `${base}/search` });
  return batch;
};

const closeAll = BrowserPool.prototype.closeAll;
BrowserPool.prototype.closeAll = async function () {
  record('closeAll-start');
  await new Promise(resolve => setTimeout(resolve, Number(process.env.STUB_CLOSEALL_DELAY ?? 0)));
  await closeAll.call(this);
  record('closeAll-end');
};
const abort = CallBudget.prototype.abort;
CallBudget.prototype.abort = function (reason) {
  record('abort', { reason: reason instanceof Error ? reason.message : String(reason ?? '') });
  return abort.call(this, reason);
};

chromium.launch = async options => {
  record('launch', { options: { channel: options?.channel, headless: options?.headless } });
  if (process.env.STUB_FAKE_BROWSER !== '1') throw new Error('stub: browser launch disabled');
  const page = {
    on: () => undefined, off: () => undefined, mainFrame: () => undefined,
    goto: async url => { record('goto', { url }); return { status: () => 200, headers: () => ({ 'content-type': 'text/html' }) }; },
    url: () => `${base}/fake`, title: async () => 'Fake', evaluate: async () => 'fake browser text',
    waitForLoadState: async () => undefined, content: async () => '<html><body><p>fake browser text</p></body></html>',
  };
  return {
    isConnected: () => true, version: () => '777.0.0.0', close: async () => undefined,
    newContext: async contextOptions => {
      record('newContext', { userAgent: contextOptions?.userAgent });
      return { newPage: async () => page, close: async () => undefined };
    },
  };
};
process.on('exit', code => record('exit', { code }));
