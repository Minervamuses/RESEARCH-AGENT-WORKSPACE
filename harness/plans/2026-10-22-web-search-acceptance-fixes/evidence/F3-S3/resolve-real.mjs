// F3-S3 real Chromium check of wrapper resolution through SearchEngine.search():
//   TMPDIR=<short dir> PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node resolve-real.mjs <dist-dir>
// The server binds 127.0.0.1 only; localhost:<port> is the test search host, targets are on 127.0.0.1:<port>.
import { createServer } from 'node:http';
import { readFileSync, readdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const dist = path.resolve(process.argv[2]);
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
const { sharedBrowserPool, OPERATION_TIMEOUTS } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const stat = pid => {
  try { const t = readFileSync(`/proc/${pid}/stat`, 'utf8'); const f = t.slice(t.lastIndexOf(')') + 1).trim().split(/\s+/); return { state: f[0], ppid: Number(f[1]), start: f[19] }; }
  catch { return undefined; }
};
const descendants = () => {
  const all = readdirSync('/proc').filter(n => /^\d+$/.test(n)).map(Number).map(pid => ({ pid, ...stat(pid) })).filter(p => p.start);
  const family = new Set([process.pid]);
  for (let grew = true; grew;) { grew = false; for (const p of all) if (!family.has(p.pid) && family.has(p.ppid)) { family.add(p.pid); grew = true; } }
  family.delete(process.pid);
  return all.filter(p => family.has(p.pid));
};
const log = [];
let port;
const target = name => `http://127.0.0.1:${port}/target/${name}`;
const server = createServer((request, response) => {
  const url = new URL(request.url, 'http://x');
  log.push({ host: request.headers.host, path: `${url.pathname}${url.search}`, referer: request.headers.referer ?? null });
  const kind = url.searchParams.get('k');
  if (url.pathname === '/search') {
    response.writeHead(200, { 'content-type': 'text/html' });
    response.end(`<html><body><div id="search">${['js', '302', 'pdf', 'hang', 'stay'].map(k => `<div><a href="/goto?k=${k}"><h3>${k}</h3></a></div>`).join('')}</div></body></html>`);
  } else if (url.pathname === '/bing') {
    response.writeHead(200, { 'content-type': 'text/html' }); response.end('<ol id="b_results"></ol>');
  } else if (url.pathname === '/goto' && kind === 'js') {
    response.writeHead(200, { 'content-type': 'text/html' }); response.end(`<script>location.replace(${JSON.stringify(target('js'))})</script>`);
  } else if (url.pathname === '/goto' && ['302', 'pdf', 'hang'].includes(kind)) {
    response.writeHead(302, { location: target({ 302: '302', pdf: 'doc.pdf', hang: 'hang' }[kind]) }); response.end();
  } else if (url.pathname === '/goto' && kind === 'stay') {
    response.writeHead(200, { 'content-type': 'text/html' }); response.end('<p>An intermediate page that needs a click.</p>');
  } else if (url.pathname === '/target/doc.pdf') {
    response.writeHead(200, { 'content-type': 'application/pdf' }); response.end('%PDF-1.7\n%fake\n');
  } else if (url.pathname === '/target/hang') {
    /* never responds */
  } else {
    response.writeHead(200, { 'content-type': 'text/html' }); response.end('<p>target</p>');
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
port = server.address().port;
SearchEngine.googleSearchUrl = `http://localhost:${port}/search`;
SearchEngine.googleHost = `localhost:${port}`;
SearchEngine.bingSearchUrl = `http://localhost:${port}/bing`;
SearchEngine.bingHost = `localhost:${port}`;
OPERATION_TIMEOUTS.linkResolve = 2000;
let result, during, elapsed;
try {
  const begin = performance.now();
  result = await new SearchEngine().search({ query: 'x', numResults: 5 });
  elapsed = Math.round(performance.now() - begin);
  during = descendants();
} finally {
  await sharedBrowserPool.closeAll();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
await new Promise(resolve => setTimeout(resolve, 300));
const survivors = during.filter(p => { const now = stat(p.pid); return now && now.start === p.start && now.state !== 'Z'; });
const portless = value => typeof value === 'string' ? value.replaceAll(String(port), '<port>') : value;
process.stdout.write(JSON.stringify({
  linkResolveMs: 2000, searchElapsedMs: elapsed,
  engines: result.engines,
  results: result.results.map(r => ({ title: r.title, url: portless(r.url), observedUrl: r.observedUrl, resolution: { ...r.resolution, wrapperUrl: portless(r.resolution?.wrapperUrl), reason: portless(r.resolution?.reason) } })),
  serverLog: log.map(entry => ({ host: portless(entry.host), path: entry.path, referer: portless(entry.referer) })),
  descendantsDuringCall: during.length, survivorsAfterCleanup: survivors,
}, null, 1) + '\n');
