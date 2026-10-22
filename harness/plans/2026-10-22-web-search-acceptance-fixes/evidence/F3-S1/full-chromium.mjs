// F3-S1 real check: BrowserPool launches full Chromium with a normal UA, and cleanup leaves no process.
//   TMPDIR=<short dir> PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node full-chromium.mjs <dist-dir>
import { createServer } from 'node:http';
import { readFileSync, readlinkSync, readdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const dist = path.resolve(process.argv[2]);
const { BrowserPool } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
const stat = pid => {
  try { const text = readFileSync(`/proc/${pid}/stat`, 'utf8'); const f = text.slice(text.lastIndexOf(')') + 1).trim().split(/\s+/); return { state: f[0], ppid: Number(f[1]), pgrp: Number(f[2]), start: f[19] }; }
  catch { return undefined; }
};
const descendants = () => {
  const all = readdirSync('/proc').filter(name => /^\d+$/.test(name)).map(Number).map(pid => ({ pid, ...stat(pid) })).filter(p => p.start);
  const family = new Set([process.pid]);
  for (let grew = true; grew;) { grew = false; for (const p of all) if (!family.has(p.pid) && family.has(p.ppid)) { family.add(p.pid); grew = true; } }
  family.delete(process.pid);
  return all.filter(p => family.has(p.pid)).map(p => {
    let exe = null; try { exe = readlinkSync(`/proc/${p.pid}/exe`).replace(process.env.HOME, '~'); } catch { /* exited */ }
    let argv = null; try { const raw = readFileSync(`/proc/${p.pid}/cmdline`, 'utf8'); argv = { nulFields: raw.split('\0').filter(Boolean).length, ownerFlagAsNulField: raw.split('\0').some(a => a.startsWith('--web-search-owner=')), ownerFlagAsSpaceToken: raw.split(/[\0 ]/).some(a => a.startsWith('--web-search-owner=')) }; } catch { /* exited */ }
    return { pid: p.pid, ppid: p.ppid, pgrp: p.pgrp, start: p.start, exe, argv };
  });
};
let headerUa;
const server = createServer((request, response) => {
  headerUa = request.headers['user-agent'];
  response.writeHead(200, { 'content-type': 'text/html' });
  response.end('<html><body><p>local page</p></body></html>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const pool = new BrowserPool();
let navigatorUa, during, owned, version;
try {
  navigatorUa = await pool.withPage(async page => {
    await page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: 'domcontentloaded' });
    return page.evaluate(() => navigator.userAgent);
  });
  version = (await pool.getBrowser()).version();
  owned = [...pool.owned.entries()].map(([pid, start]) => ({ pid, start, exe: (() => { try { return readlinkSync(`/proc/${pid}/exe`).replace(process.env.HOME, '~'); } catch { return null; } })() }));
  during = descendants();
} finally {
  await pool.closeAll();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
await new Promise(resolve => setTimeout(resolve, 300));
const survivors = during.filter(p => { const now = stat(p.pid); return now && now.start === p.start && now.state !== 'Z'; });
const out = {
  browserVersion: version, navigatorUa, headerUa,
  navigatorHasHeadless: /Headless/.test(navigatorUa), headerHasHeadless: /Headless/.test(headerUa ?? ''),
  // The pool's own record; empty when Chromium rewrote its argv (AF22, fixed in F4-S2).
  poolOwned: owned,
  browserRoot: during.find(p => p.ppid === process.pid && /chrome/.test(p.exe ?? '')) ?? null,
  fullChromium: during.some(p => /ms-playwright\/chromium-\d+\//.test(p.exe ?? '')) && !during.some(p => /headless_shell/.test(p.exe ?? '')),
  descendantsDuringCall: during.length, distinctExecutables: [...new Set(during.map(p => p.exe))],
  survivorsAfterCleanup: survivors,
};
process.stdout.write(JSON.stringify(out, null, 1) + '\n');
