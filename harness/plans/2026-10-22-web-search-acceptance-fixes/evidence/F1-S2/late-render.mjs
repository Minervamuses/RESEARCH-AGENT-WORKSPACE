// Real Chromium late-render matrix through the product extractor:
//   PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node late-render.mjs <dist-dir> [label]
// Every HTML response has no text of its own, so the HTTP read is empty_text and the browser fallback runs.
import { createServer } from 'node:http';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const dist = path.resolve(process.argv[2]);
const label = process.argv[3] ?? 'build';
const { EnhancedContentExtractor } = await import(pathToFileURL(path.join(dist, 'enhanced-content-extractor.js')).href);
const { sharedBrowserPool, CallBudget } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const insert = (ms, text) => `<script>setTimeout(() => document.body.insertAdjacentHTML('beforeend', '<p>${text}</p>'), ${ms});</script>`;
const fetchInsert = (ms, text) => `<script>fetch('/data?ms=${ms}&text=${text}').then(r => r.text()).then(t => document.body.insertAdjacentHTML('beforeend', '<p>' + t + '</p>'));</script>`;
const pages = {
  'timer-0': { html: insert(0, 'TARGET timer 0') },
  'timer-100': { html: insert(100, 'TARGET timer 100') },
  'timer-300': { html: insert(300, 'TARGET timer 300') },
  'timer-700': { html: insert(700, 'TARGET timer 700') },
  'timer-1500': { html: insert(1500, 'TARGET timer 1500') },
  'fetch-200': { html: fetchInsert(200, 'TARGET fetch 200') },
  'nav-then-fetch-300': {
    html: `<script>document.write('<nav>Site menu Home About</nav>');</script>${fetchInsert(300, 'TARGET main after nav')}`,
  },
  'csp-timer-300': { html: insert(300, 'TARGET csp timer 300'), headers: { 'Content-Security-Policy': "script-src 'unsafe-inline'" } },
  'timer-5000': { html: insert(5000, 'TARGET beyond limit') },
  'polling-forever': {
    html: `${insert(0, 'TARGET with endless polling')}<script>setInterval(() => fetch('/data?ms=150&text=x'), 200);</script>`,
  },
};
const server = createServer((request, response) => {
  const url = new URL(request.url, 'http://127.0.0.1');
  if (url.pathname === '/data') {
    setTimeout(() => { response.writeHead(200, { 'content-type': 'text/plain' }); response.end(url.searchParams.get('text')); },
      Number(url.searchParams.get('ms')));
    return;
  }
  if (url.pathname === '/static') {
    response.writeHead(200, { 'content-type': 'text/html' });
    response.end('<html><head><title>Static</title></head><body><p>TARGET static text</p></body></html>');
    return;
  }
  const page = pages[url.pathname.slice(1)];
  if (!page) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', ...(page.headers ?? {}) });
  response.end(`<html><head><title>${url.pathname.slice(1)}</title></head><body>${page.html}</body></html>`);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const extractor = new EnhancedContentExtractor();
const rows = [];
const summarize = (name, read, ms) => ({
  case: name, status: read.status, ms: Math.round(ms), attempts: read.attempts.map(a => a.transport),
  target: /TARGET/.test(read.content), content: read.content.slice(0, 120), error: read.error ?? null,
});
try {
  // Warm the browser once so launch time is not charged to the first case.
  await extractor.extractContent({ url: `${base}/timer-0` });
  for (const name of Object.keys(pages)) {
    const begin = performance.now();
    const read = await extractor.extractContent({ url: `${base}/${name}` });
    rows.push(summarize(name, read, performance.now() - begin));
  }
  let begin = performance.now();
  const httpStatic = await extractor.extractContent({ url: `${base}/static` });
  rows.push(summarize('static-http-has-text', httpStatic, performance.now() - begin));
  // Static page forced through the browser path to measure the added settle latency.
  const state = { requestedUrl: `${base}/static`, status: 'not_attempted', attempts: [], content: '', maxContentLength: 10000, returnedLength: 0, truncated: false };
  const budget = new CallBudget(20000);
  begin = performance.now();
  const text = await extractor.extractWithBrowser({ url: `${base}/static`, budget }, state, () => undefined, { transport: 'browser' });
  rows.push({ case: 'static-browser-direct', ms: Math.round(performance.now() - begin), target: /TARGET/.test(text), content: text.slice(0, 120) });
  budget.dispose();
} finally {
  await sharedBrowserPool.closeAll();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
process.stdout.write(JSON.stringify({ label, node: process.version, rows }, null, 1) + '\n');
