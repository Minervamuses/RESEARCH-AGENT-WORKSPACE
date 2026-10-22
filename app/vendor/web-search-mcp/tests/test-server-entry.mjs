// Entry tests for dist/index.js: tool wiring, budgets, settings and shutdown, with stubbed engines.
// Usage: node tests/test-server-entry.mjs [dist-directory]   (or WEB_SEARCH_DIST=<dist-directory>)
// No public network and no Chromium: tests/fixtures/stub-engines.mjs replaces engines and browser launch.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(process.argv[2] ?? process.env.WEB_SEARCH_DIST ?? path.join(here, '..', 'dist'));
const entry = path.join(dist, 'index.js');
const preload = pathToFileURL(path.join(here, 'fixtures', 'stub-engines.mjs')).href;
const scratch = mkdtempSync(path.join(os.tmpdir(), 'ws-entry-'));
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let logCount = 0;
const newLog = () => { const file = path.join(scratch, `log-${++logCount}.jsonl`); writeFileSync(file, ''); return file; };
const events = file => readFileSync(file, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
const waitFor = async (check, ms, what) => {
  const end = Date.now() + ms;
  while (Date.now() < end) { const value = check(); if (value) return value; await pause(10); }
  throw new Error(`timed out waiting for ${what}`);
};

// Local pages: /page/<n> is text, /long has 30 code points, /empty has no text, /stuck never answers.
const requests = [];
const stuck = [];
const server = createServer((request, response) => {
  requests.push(request.url);
  if (request.url === '/stuck') {
    const record = { opened: Date.now(), closed: undefined };
    stuck.push(record);
    request.socket.once('close', () => { record.closed = Date.now(); });
    return;
  }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
  if (request.url === '/empty') response.end('<html><body></body></html>');
  else if (request.url === '/long') response.end('<p>😀中文abcdefghijklmnopqrstuvwxyz0</p>');
  else response.end(`<html><head><title>Page ${request.url}</title></head><body><p>Body of ${request.url}</p></body></html>`);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const pageRequests = () => requests.filter(url => url.startsWith('/page/')).length;

const childEnv = (log, extra = {}) => ({ STUB_LOG: log, STUB_PAGE_BASE: base, ...extra });
async function connect(extra = {}) {
  const log = newLog();
  const transport = new StdioClientTransport({
    command: process.execPath, args: ['--import', preload, entry], env: childEnv(log, extra), stderr: 'ignore',
  });
  // index.ts prints banners to stdout; the SDK reports them here and they are not failures.
  transport.onerror = () => undefined;
  const client = new Client({ name: 'server-entry-test', version: '1' });
  await client.connect(transport);
  return { client, log };
}
const text = result => result.content.map(part => part.text).join('\n');
const fails = async promise => {
  try { const result = await promise; return result.isError === true; } catch { return true; }
};

const cases = [];
const check = (name, fn) => cases.push({ name, fn });

check('wiring: includeContent, summaries, engine lines, invalid input and single-page limits', async () => {
  const { client, log } = await connect();
  try {
    // 1. includeContent=false reads nothing (AF29, N13, N14f); true reads the same candidates in order.
    let before = pageRequests();
    const unread = text(await client.callTool({ name: 'full-web-search', arguments: { query: 'alpha', includeContent: false } }));
    assert.equal(pageRequests(), before);
    const urls = value => [...value.matchAll(/^URL: (.+)$/gm)].map(match => match[1]);
    assert.deepEqual(urls(unread), [1, 2, 3, 4].map(id => `${base}/page/${id}`));
    assert.equal(unread.match(/^Read status: not_attempted$/gm).length, 4);
    assert.doesNotMatch(unread, /\*\*Page content:\*\*/);
    before = pageRequests();
    const read = text(await client.callTool({ name: 'full-web-search', arguments: { query: 'alpha' } }));
    assert.equal(pageRequests() - before, 4);
    assert.deepEqual(urls(read), urls(unread));
    assert.match(read, /\*\*Page content:\*\*\nBody of \/page\/1/);
    // 2. summaries never read pages and pass the limit; both tools show engine lines (N13b, N14g, N14h, N14i).
    before = pageRequests();
    const summaries = text(await client.callTool({ name: 'get-web-search-summaries', arguments: { query: 'alpha', limit: 2 } }));
    assert.equal(pageRequests(), before);
    assert.match(summaries, /^Search for "alpha": 2 candidates$/m);
    assert.match(summaries, /^- Google: attempted=true; attempts=1; parsed_count=4; status=completed$/m);
    assert.equal(summaries.match(/^- \w+: attempted=/gm).length, 1);
    assert.match(read, /^- Google: attempted=true; attempts=1; parsed_count=4; status=completed$/m);
    // 3/4. Invalid limit on both tools and a blank summaries query fail before any engine runs (AF14).
    const engineCalls = () => events(log).filter(e => e.event === 'engine').length;
    const calls = engineCalls();
    assert.ok(await fails(client.callTool({ name: 'full-web-search', arguments: { query: 'alpha', limit: 11 } })));
    assert.ok(await fails(client.callTool({ name: 'get-web-search-summaries', arguments: { query: 'alpha', limit: 11 } })));
    assert.ok(await fails(client.callTool({ name: 'get-web-search-summaries', arguments: { query: '   ' } })));
    assert.equal(engineCalls(), calls);
    // 5a. An explicit single-page limit is honoured (N14d).
    const limited = text(await client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/long`, maxContentLength: 7 } }));
    assert.match(limited, /Markdown length: returned=7; original=30; limit=7 Unicode code points/);
    // 14. Tool texts promise no completeness and keep the citation routing sentence (AF39, Node part).
    const { tools } = await client.listTools();
    assert.deepEqual(tools.map(tool => tool.name).sort(), ['full-web-search', 'get-single-web-page-content', 'get-web-search-summaries']);
    for (const tool of tools) {
      const wording = [tool.description, ...Object.values(tool.inputSchema.properties ?? {}).map(p => p.description ?? '')].join('\n');
      assert.doesNotMatch(wording, /comprehensive|complete full text|full page content|verified|authoritative|high.quality/i, tool.name);
      assert.ok(tool.description.includes('Use citation_workflow for paper discovery, bibliographic metadata, abstracts and citations.'), tool.name);
    }
    // 6. No handler closes the pool; it closes only at shutdown, once (N12, N11e).
    assert.equal(events(log).filter(e => e.event.startsWith('closeAll')).length, 0);
  } finally { await client.close(); }
  await waitFor(() => events(log).some(e => e.event === 'exit'), 5000, 'server exit');
  assert.deepEqual(events(log).filter(e => e.event.startsWith('closeAll')).map(e => e.event), ['closeAll-start', 'closeAll-end']);
});

check('deployed MAX_CONTENT_LENGTH applies when the single-page limit is omitted', async () => {
  const { client } = await connect({ MAX_CONTENT_LENGTH: '9' });
  try {
    const deployed = text(await client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/long` } }));
    assert.match(deployed, /Markdown length: returned=9; original=30; limit=9 Unicode code points/);
  } finally { await client.close(); }
});

check('_meta work budget, transport cancellation and the cleanup reserve bound a stuck read', async () => {
  // 9. _meta.web_search_work_ms bounds the call even with the default 300000 ms budget (N14, N14b).
  const { client } = await connect();
  try {
    let begin = Date.now();
    const timed = text(await client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/stuck` }, _meta: { web_search_work_ms: 300 } }));
    assert.ok(Date.now() - begin < 1000, `meta-bounded call took ${Date.now() - begin} ms`);
    assert.match(timed, /Page read status: timeout/);
    // 10. A transport-level cancellation aborts the server's read and closes its connection (N14c).
    const controller = new AbortController();
    const opened = stuck.length;
    const call = client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/stuck` } }, undefined, { signal: controller.signal });
    call.catch(() => undefined);
    const connection = await waitFor(() => stuck[opened], 3000, 'stuck connection');
    begin = Date.now();
    controller.abort();
    await assert.rejects(call);
    await waitFor(() => connection.closed, 1000, 'server-side close after cancellation');
    assert.ok(connection.closed - begin < 500, `cancellation closed the read after ${connection.closed - begin} ms`);
  } finally { await client.close(); }
  // 12. DEFAULT_TIMEOUT=2000 leaves 1000 ms of work after its cleanup reserve (N42 would wait ~2000 ms).
  const reserve = await connect({ DEFAULT_TIMEOUT: '2000' });
  try {
    const begin = Date.now();
    await reserve.client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/stuck` } });
    const elapsed = Date.now() - begin;
    assert.ok(elapsed >= 800 && elapsed < 1500, `reserve-bounded call took ${elapsed} ms`);
  } finally { await reserve.client.close(); }
});

check('browser fallback launches full Chromium with the configured headless mode and a normal UA', async () => {
  for (const [headless, expected] of [['false', false], [undefined, true]]) {
    const { client, log } = await connect({ STUB_FAKE_BROWSER: '1', ...(headless ? { BROWSER_HEADLESS: headless } : {}) });
    try {
      const read = text(await client.callTool({ name: 'get-single-web-page-content', arguments: { url: `${base}/empty` } }));
      assert.match(read, /fake browser text/);
    } finally { await client.close(); }
    const recorded = events(log);
    assert.deepEqual(recorded.find(e => e.event === 'launch').options, { channel: 'chromium', headless: expected });
    const { userAgent } = recorded.find(e => e.event === 'newContext');
    assert.match(userAgent, /Chrome\/777\.0\.0\.0/);
    assert.doesNotMatch(userAgent, /Headless/);
  }
});

// Lifecycle cases speak newline-delimited JSON-RPC to a spawned server (the SDK close() also signals).
async function startRaw(extra = {}) {
  const log = newLog();
  const child = spawn(process.execPath, ['--import', preload, entry], { env: childEnv(log, extra), stdio: ['pipe', 'pipe', 'ignore'] });
  const exited = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal, at: Date.now() })));
  const send = message => child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', ...message })}\n`);
  send({ id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'raw', version: '1' } } });
  send({ method: 'notifications/initialized' });
  return { child, log, exited, send };
}
for (const [stop, protects] of [['stdin', 'N11b, N11d'], ['SIGTERM', 'N11c']]) {
  check(`${stop} during a stuck read aborts it before the bounded pool close and exits 0 (${protects})`, async () => {
    const { child, log, exited, send } = await startRaw({ STUB_CLOSEALL_DELAY: '1500' });
    const opened = stuck.length;
    send({ id: 2, method: 'tools/call', params: { name: 'get-single-web-page-content', arguments: { url: `${base}/stuck` } } });
    const connection = await waitFor(() => stuck[opened], 5000, 'stuck connection');
    const stopped = Date.now();
    if (stop === 'stdin') child.stdin.end(); else child.kill('SIGTERM');
    const exit = await Promise.race([exited, pause(6000).then(() => undefined)]);
    if (!exit) child.kill('SIGKILL');
    assert.ok(exit, `${stop}: the server did not exit`);
    assert.equal(exit.code, 0);
    const recorded = events(log);
    const closeEnd = recorded.find(e => e.event === 'closeAll-end');
    const aborted = recorded.find(e => e.event === 'abort');
    assert.ok(aborted && closeEnd, `${stop}: abort and closeAll recorded`);
    assert.ok(aborted.at < closeEnd.at, 'the active call is aborted before the pool close returns');
    assert.ok(connection.closed !== undefined && connection.closed - stopped < 300, `${stop}: read closed after ${connection.closed - stopped} ms`);
    assert.ok(exit.at >= closeEnd.at && exit.at - stopped < 4000, `${stop}: exit after ${exit.at - stopped} ms`);
  });
}

check('invalid deployment settings stop the server at startup (N43, N05d, N08i)', async () => {
  for (const extra of [{ DEFAULT_TIMEOUT: '300001' }, { MAX_CONTENT_LENGTH: '0' }, { BROWSER_HEADLESS: 'maybe' }]) {
    const { child, exited } = await startRaw(extra);
    const exit = await Promise.race([exited, pause(5000).then(() => undefined)]);
    if (!exit) child.kill('SIGKILL');
    assert.ok(exit && exit.code !== 0, `${JSON.stringify(extra)} was accepted`);
  }
});

let failed = 0;
try {
  for (const { name, fn } of cases) {
    try { await fn(); process.stdout.write(`ok - ${name}\n`); }
    catch (error) { failed++; process.stdout.write(`not ok - ${name}\n${error.stack}\n`); }
  }
} finally {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
  rmSync(scratch, { recursive: true, force: true });
}
process.stdout.write(`${cases.length - failed}/${cases.length} passed (${dist})\n`);
process.exitCode = failed ? 1 : 0;
