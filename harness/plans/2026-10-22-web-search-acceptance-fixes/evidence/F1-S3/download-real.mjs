// Early real Chromium probe of AF10(b): HTTP 403 for the HTTP read, then a PDF or octet-stream for the browser.
//   TMPDIR=<short dir> PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node download-real.mjs <dist-dir>
// The formal acceptance is F7-S2 case 7 through the real Python entry.
import { createServer } from 'node:http';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const dist = path.resolve(process.argv[2]);
const { EnhancedContentExtractor } = await import(pathToFileURL(path.join(dist, 'enhanced-content-extractor.js')).href);
const { sharedBrowserPool } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const server = createServer((request, response) => {
  // The HTTP reader announces Chrome/121; the browser announces its real major version.
  if (/Chrome\/121\./.test(request.headers['user-agent'] ?? '')) { response.writeHead(403, { 'content-type': 'text/html' }); response.end('<p>denied</p>'); return; }
  if (request.url === '/doc.pdf') { response.writeHead(200, { 'content-type': 'application/pdf' }); response.end('%PDF-1.7\n%fake\n'); return; }
  response.writeHead(200, { 'content-type': 'application/octet-stream', 'content-disposition': 'attachment; filename="x.bin"' });
  response.end(Buffer.alloc(1024));
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const rows = [];
try {
  for (const route of ['/doc.pdf', '/file.bin']) {
    const read = await new EnhancedContentExtractor().extractContent({ url: `${base}${route}` });
    rows.push({ route, status: read.status, httpStatus: read.httpStatus ?? null, contentType: read.contentType ?? null, error: read.error ?? null,
      attempts: read.attempts.map(a => ({ transport: a.transport, status: a.status ?? null, error: a.error ?? null })) });
  }
} finally {
  await sharedBrowserPool.closeAll();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
process.stdout.write(JSON.stringify(rows, null, 1).replaceAll(base, 'http://127.0.0.1:<port>') + '\n');
