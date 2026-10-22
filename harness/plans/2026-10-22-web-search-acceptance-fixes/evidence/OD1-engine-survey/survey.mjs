// Engine x browser-mode survey for decision OD1 (read-only; paced public requests).
// Usage (outside the host sandbox, short TMPDIR — Chrome's singleton socket path must stay short):
//   T=$(mktemp -d /tmp/sv.XXXX); TMPDIR=$T PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright \
//   node survey.mjs <output-dir>
// Uses the vendored dist parsers and product engine methods; changes no product file.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const VENDOR = '/home/minervamuses/research-agent-workspace/app/vendor/web-search-mcp';
const OUT = path.resolve(process.argv[2] ?? '.');
const require = createRequire(path.join(VENDOR, 'package.json'));
const cheerio = require('cheerio');
const axios = (await import(path.join(VENDOR, 'node_modules/axios/index.js'))).default;
const { chromium } = await import(path.join(VENDOR, 'node_modules/playwright/index.mjs'));
const { SearchEngine } = await import(path.join(VENDOR, 'dist/search-engine.js'));
const { BrowserPool, CallBudget } = await import(path.join(VENDOR, 'dist/browser-pool.js'));
const { EnhancedContentExtractor } = await import(path.join(VENDOR, 'dist/enhanced-content-extractor.js'));

// Keep product diagnostics out of the report; our own lines go to stdout via write().
const say = text => process.stdout.write(text + '\n');
console.log = () => {};
console.error = () => {};
console.warn = () => {};

const QUERIES = [
  { q: 'python asyncio cancel task', lang: 'en', terms: ['asyncio', 'cancel'] },
  { q: '台灣 颱風 最新消息', lang: 'zh', terms: ['颱風'] },
  { q: 'how does photosynthesis work', lang: 'en', terms: ['photosynthesis'] },
  { q: '機器學習 過擬合 解決方法', lang: 'zh', terms: ['過擬合', '過度擬合', 'overfitting'] },
  { q: 'Playwright headless detection', lang: 'en', terms: ['playwright', 'headless'] },
  { q: '台北 捷運 路線圖', lang: 'zh', terms: ['捷運'] },
];
const ENGINE_HOSTS = {
  bing: ['bing.com'], brave: ['brave.com'], ddg: ['duckduckgo.com'], google: ['google.com'], mojeek: ['mojeek.com'],
};
const HTTP_UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36';

// Browser mode is injected at launch; UA override (if any) at context creation.
const realLaunch = chromium.launch.bind(chromium);
let launchMode = 'headless_shell';
let uaOverride = false;
chromium.launch = async (options = {}) => {
  const channel = { full_chromium: 'chromium', system_chrome: 'chrome' }[launchMode];
  const browser = await realLaunch({ ...options, ...(channel ? { channel } : {}) });
  if (uaOverride) {
    const major = browser.version().split('.')[0];
    const ua = `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
    const newContext = browser.newContext.bind(browser);
    browser.newContext = (opts = {}) => newContext({ userAgent: ua, ...opts });
  }
  return browser;
};
const pools = new Map();
const versions = {};
async function poolFor(mode, ua = false) {
  const key = `${mode}${ua ? '+ua' : ''}`;
  if (!pools.has(key)) {
    const pool = new BrowserPool();
    launchMode = mode; uaOverride = ua;
    const budget = new CallBudget(30000);
    try { versions[key] = (await pool.getBrowser(budget)).version(); } finally { budget.dispose(); launchMode = 'headless_shell'; uaOverride = false; }
    pools.set(key, pool);
  }
  return pools.get(key);
}

// Observe the last main-frame navigation of a product engine call without changing it.
function observe(pool) {
  const info = {};
  const withPage = pool.withPage.bind(pool);
  return {
    info,
    pool: Object.assign(Object.create(pool), {
      withPage: (fn, budget) => withPage(async (page, context) => {
        page.on('response', response => {
          if (response.request().isNavigationRequest() && response.frame() === page.mainFrame()) info.status = response.status();
        });
        try { return await fn(page, context); } finally {
          info.finalUrl = page.url();
          info.pageTitle = await page.title().catch(() => undefined);
        }
      }, budget),
    }),
  };
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const lastHit = {};
let lastAny = 0;
async function pace(host, gap = 5000) {
  const wait = Math.max((lastHit[host] ?? 0) + gap - Date.now(), lastAny + 1000 - Date.now(), 0);
  if (wait) await sleep(wait);
  lastHit[host] = lastAny = Date.now();
}
const short = (text, n) => (text ?? '').replace(/\s+/g, ' ').trim().slice(0, n);
const hostPath = url => { try { const u = new URL(url); return { host: u.hostname, path: short(u.pathname, 60) }; } catch { return { host: 'invalid', path: '' }; } };

function summarise(engine, items, query) {
  const own = ENGINE_HOSTS[engine];
  const isWrapper = url => { const { host } = hostPath(url); return own.some(h => host === h || host.endsWith('.' + h)); };
  const direct = items.filter(item => !isWrapper(item.url));
  const relevant = items.filter(item => query.terms.some(t => `${item.title} ${item.description}`.toLowerCase().includes(t.toLowerCase())));
  return {
    n: items.length, nDirect: direct.length,
    domains: [...new Set(direct.map(item => hostPath(item.url).host))].slice(0, 10),
    wrapperHosts: [...new Set(items.filter(item => isWrapper(item.url)).map(item => hostPath(item.url).host))],
    relevance: items.length ? Number((relevant.length / items.length).toFixed(2)) : 0,
    sample: items.slice(0, 3).map(item => ({ title: short(item.title, 80), ...hostPath(item.url) })),
    directUrls: direct.map(item => item.url),
  };
}

// Parser-independent hint: external result-like links on the page (guards against a wrong ad-hoc selector).
function externalLinks(html, engine) {
  const $ = cheerio.load(html);
  const own = ENGINE_HOSTS[engine];
  const hosts = new Set();
  $('a[href^="http"]').each((_i, a) => {
    const { host } = hostPath($(a).attr('href'));
    if (!own.some(h => host === h || host.endsWith('.' + h))) hosts.add(host);
  });
  return hosts.size;
}

// Ad-hoc parsers for exploratory engines (analysis only; not product code).
function parseGoogle(html) {
  const $ = cheerio.load(html);
  const out = [];
  $('a:has(h3)').each((_i, a) => {
    const href = $(a).attr('href') ?? '';
    if (!/^https?:/.test(href)) return;
    const block = $(a).closest('div.g, div[data-hveid], div.MjjYud');
    out.push({ title: $(a).find('h3').first().text(), url: href, description: block.find('.VwiC3b, [data-sncf]').first().text() });
  });
  return out;
}
function parseMojeek(html, base) {
  const $ = cheerio.load(html);
  return $('ul.results-standard li').map((_i, li) => {
    const a = $(li).find('a.title, h2 a').first();
    const href = a.attr('href');
    return href ? { title: a.text(), url: new URL(href, base).href, description: $(li).find('p.s').first().text() } : null;
  }).get().filter(Boolean);
}
function parseDdgLite(html, base) {
  const $ = cheerio.load(html);
  const engine = new SearchEngine();
  return $('a.result-link').map((_i, a) => {
    const href = $(a).attr('href');
    if (!href) return null;
    const row = $(a).closest('tr');
    return { title: $(a).text(), url: engine.cleanDuckDuckGoUrl(href, base), description: row.nextAll('tr').first().find('td.result-snippet').text() };
  }).get().filter(Boolean);
}

async function runSearch(combo, query) {
  const facts = {};
  let items = [];
  if (combo.engine === 'bing' || combo.engine === 'brave') {
    const { info, pool } = observe(await poolFor(combo.mode, combo.ua));
    await pace(combo.engine);
    const engine = new SearchEngine(pool);
    const state = { attempts: 0 };
    const budget = new CallBudget(25000);
    try {
      items = combo.engine === 'bing'
        ? await engine.tryBrowserBingSearch(query.q, 10, 4000, state, budget)
        : await engine.tryBrowserBraveSearch(query.q, 10, 4000, state, budget);
    } finally { budget.dispose(); Object.assign(facts, info, { transportAttempts: state.attempts }); }
  } else if (combo.engine === 'google' || (combo.engine === 'ddg' && combo.mode === 'system_chrome')) {
    const { info, pool } = observe(await poolFor(combo.mode, combo.ua));
    await pace(combo.engine);
    const url = combo.engine === 'google'
      ? `https://www.google.com/search?q=${encodeURIComponent(query.q)}&hl=${query.lang === 'zh' ? 'zh-TW' : 'en'}&num=10`
      : `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query.q)}`;
    const budget = new CallBudget(25000);
    try {
      const html = await pool.withPage(async page => {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        if (combo.engine === 'google') await page.waitForSelector('a h3', { timeout: 4000 }).catch(() => undefined);
        return page.content();
      }, budget);
      items = combo.engine === 'google' ? parseGoogle(html) : new SearchEngine().parseDuckDuckGoResults(html, 10, info.finalUrl ?? url);
      Object.assign(facts, { bodyLength: html.length, externalLinks: externalLinks(html, combo.engine) });
    } finally { budget.dispose(); Object.assign(facts, info); }
  } else {
    // Plain HTTP variants: DuckDuckGo GET (product-equivalent), POST, lite; Mojeek.
    const request = {
      http_get: () => axios.get('https://html.duckduckgo.com/html/', { params: { q: query.q } }),
      http_post: () => axios.post('https://html.duckduckgo.com/html/', new URLSearchParams({ q: query.q })),
      http_lite: () => axios.get('https://lite.duckduckgo.com/lite/', { params: { q: query.q } }),
      mojeek: () => axios.get('https://www.mojeek.com/search', { params: { q: query.q } }),
    }[combo.engine === 'mojeek' ? 'mojeek' : combo.mode];
    await pace(combo.engine);
    axios.defaults.headers.common['User-Agent'] = HTTP_UA;
    const response = await request.call(null).catch(error => error.response ?? Promise.reject(error));
    const finalUrl = response.request?.res?.responseUrl;
    Object.assign(facts, { status: response.status, finalUrl, bodyLength: String(response.data ?? '').length });
    const html = String(response.data ?? '');
    items = response.status >= 400 ? []
      : combo.engine === 'mojeek' ? parseMojeek(html, finalUrl ?? 'https://www.mojeek.com/')
      : combo.mode === 'http_lite' ? parseDdgLite(html, finalUrl ?? 'https://lite.duckduckgo.com/lite/')
      : new SearchEngine().parseDuckDuckGoResults(html, 10, finalUrl ?? 'https://html.duckduckgo.com/html/');
    facts.anomalyPage = /anomaly/i.test(html.slice(0, 20000)) || undefined;
    facts.externalLinks = externalLinks(html, combo.engine);
  }
  return { facts, items };
}

function classify(facts, summary, error) {
  if (error) return /HTTP 4\d\d|429|403/.test(error) ? 'blocked' : 'error';
  if (/\/sorry\/|captcha|challenge/i.test(facts.finalUrl ?? '') || (facts.status && facts.status >= 400) || facts.status === 202 || facts.anomalyPage) return 'blocked';
  return summary.n ? 'results' : 'zero';
}

const resultsFile = path.join(OUT, 'results.jsonl');
const readsFile = path.join(OUT, 'reads.jsonl');
fs.mkdirSync(OUT, { recursive: true });
const records = [];
const append = (file, record) => fs.appendFileSync(file, JSON.stringify(record) + '\n');

async function runPhase(phase, round, combos, queryIndexes) {
  const consecutiveBlocked = {};
  for (const qi of queryIndexes) {
    for (const combo of combos) {
      if ((combo.queries && !combo.queries.includes(qi)) || (consecutiveBlocked[combo.id] ?? 0) >= 2) continue;
      const query = QUERIES[qi];
      const started = Date.now();
      let facts = {}, items = [], error;
      try { ({ facts, items } = await runSearch(combo, query)); } catch (e) { error = short(e?.message ?? String(e), 200); }
      const summary = summarise(combo.engine, items, query);
      const outcome = classify(facts, summary, error);
      consecutiveBlocked[combo.id] = outcome === 'blocked' ? (consecutiveBlocked[combo.id] ?? 0) + 1 : 0;
      const { directUrls, ...kept } = summary;
      const record = {
        phase, round, combo: combo.id, engine: combo.engine, mode: combo.mode, ua: !!combo.ua, qIndex: qi, query: query.q,
        startedAt: new Date(started).toISOString(), ms: Date.now() - started, outcome, error,
        status: facts.status, final: facts.finalUrl ? hostPath(facts.finalUrl) : undefined,
        pageTitle: short(facts.pageTitle, 80) || undefined, transportAttempts: facts.transportAttempts,
        bodyLength: facts.bodyLength, externalLinks: facts.externalLinks, ...kept,
      };
      append(resultsFile, record);
      records.push({ ...record, directUrls });
      say(`${phase}/r${round} ${combo.id.padEnd(12)} q${qi} ${outcome.padEnd(7)} n=${summary.n} direct=${summary.nDirect} rel=${summary.relevance} status=${facts.status ?? '-'} ext=${facts.externalLinks ?? '-'} ${record.ms}ms${error ? ' ' + error.slice(0, 80) : ''}`);
    }
  }
}

const BASE = [
  { id: 'B-shell', engine: 'bing', mode: 'headless_shell' },
  { id: 'B-chromium', engine: 'bing', mode: 'full_chromium' },
  { id: 'B-chrome', engine: 'bing', mode: 'system_chrome' },
  { id: 'R-shell', engine: 'brave', mode: 'headless_shell' },
  { id: 'R-chromium', engine: 'brave', mode: 'full_chromium' },
  { id: 'R-chrome', engine: 'brave', mode: 'system_chrome' },
  { id: 'D-get', engine: 'ddg', mode: 'http_get' },
  { id: 'D-post', engine: 'ddg', mode: 'http_post' },
  { id: 'D-lite', engine: 'ddg', mode: 'http_lite' },
  { id: 'D-chrome', engine: 'ddg', mode: 'system_chrome' },
  { id: 'M-get', engine: 'mojeek', mode: 'http_get' },
  { id: 'G-chrome', engine: 'google', mode: 'system_chrome', queries: [0, 1, 2] },
];
const UA_VARIANTS = [
  { id: 'B-chrome-ua', engine: 'bing', mode: 'system_chrome', ua: true },
  { id: 'R-chrome-ua', engine: 'brave', mode: 'system_chrome', ua: true },
  { id: 'G-chrome-ua', engine: 'google', mode: 'system_chrome', ua: true },
];
const rate = (combo, round) => {
  const rows = records.filter(r => r.combo === combo && r.round === round);
  return rows.length ? rows.filter(r => r.outcome === 'results').length / rows.length : 0;
};

const t0 = Date.now();
say(`survey start ${new Date(t0).toISOString()}`);
await runPhase('A', 1, BASE, [0, 1, 2, 3, 4, 5]);
await runPhase('B', 1, UA_VARIANTS, [0, 1, 2]);
const stable = [...BASE, ...UA_VARIANTS].filter(c => c.engine !== 'google' && rate(c.id, 1) >= 0.5);
say(`round 2 combos: ${stable.map(c => c.id).join(', ') || '(none)'}`);
await runPhase('C', 2, stable, [0, 1, 2, 3, 4, 5]);

// Practicality: can the agent actually read what the best combos return?
const score = combo => rate(combo, 1) * (records.filter(r => r.combo === combo && r.n).reduce((s, r) => s + r.nDirect / r.n, 0) / Math.max(1, records.filter(r => r.combo === combo && r.n).length));
const best = [...new Set(records.map(r => r.combo))].filter(c => !c.startsWith('G-')).sort((a, b) => score(b) - score(a)).slice(0, 3);
say(`practicality combos: ${best.join(', ')}`);
const extractor = new EnhancedContentExtractor(new BrowserPool());
for (const combo of best) {
  for (const qi of [0, 1, 3]) {
    const row = records.find(r => r.combo === combo && r.qIndex === qi && r.round === 1 && r.directUrls.length);
    for (const url of row?.directUrls.slice(0, 3) ?? []) {
      await pace(hostPath(url).host, 2000);
      const started = Date.now();
      const budget = new CallBudget(20000);
      let read;
      try { read = await extractor.extractContent({ url, maxContentLength: 2000, budget }); } catch (e) { read = { status: 'error', error: short(e.message, 120) }; } finally { budget.dispose(); }
      const record = {
        combo, qIndex: qi, target: hostPath(url), ms: Date.now() - started, status: read.status,
        final: read.finalUrl ? hostPath(read.finalUrl) : undefined, httpStatus: read.httpStatus, returnedLength: read.returnedLength,
        attempts: read.attempts?.map(a => a.transport).join('>'), error: short(read.error, 120) || undefined,
      };
      append(readsFile, record);
      say(`read ${combo.padEnd(12)} q${qi} ${record.target.host.slice(0, 32).padEnd(32)} ${String(read.status).padEnd(16)} len=${read.returnedLength ?? 0} ${record.ms}ms`);
    }
  }
}

// Bing ck/a wrappers: does a real browser navigation reach the target page?
const ckRow = records.find(r => r.engine === 'bing' && r.round === 1 && r.wrapperHosts?.length);
if (ckRow) {
  const pool = await poolFor('system_chrome');
  const wrapperItems = (await runSearch({ engine: 'bing', mode: 'system_chrome' }, QUERIES[ckRow.qIndex]).catch(() => ({ items: [] }))).items
    .filter(item => hostPath(item.url).host.endsWith('bing.com')).slice(0, 3);
  for (const item of wrapperItems) {
    await pace('bing');
    const started = Date.now();
    const budget = new CallBudget(20000);
    let final;
    try {
      final = await pool.withPage(async page => {
        await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        await page.waitForURL(u => !u.hostname.endsWith('bing.com'), { timeout: 6000 }).catch(() => undefined);
        return page.url();
      }, budget);
    } catch (e) { final = 'error: ' + short(e.message, 80); } finally { budget.dispose(); }
    const record = { combo: 'B-chrome', kind: 'ck-a-browser-navigation', qIndex: ckRow.qIndex, ms: Date.now() - started, final: final.startsWith('error') ? final : hostPath(final) };
    append(readsFile, record);
    say(`ck/a nav -> ${JSON.stringify(record.final)} ${record.ms}ms`);
  }
}

for (const pool of pools.values()) await pool.closeAll().catch(() => undefined);
await extractor.browserPool?.closeAll?.().catch?.(() => undefined);
const combos = [...new Set(records.map(r => r.combo))];
const summary = {
  startedAt: new Date(t0).toISOString(), finishedAt: new Date().toISOString(), seconds: Math.round((Date.now() - t0) / 1000),
  browserVersions: versions, searches: records.length,
  combos: combos.map(id => {
    const rows = records.filter(r => r.combo === id);
    const byRound = round => rows.filter(r => r.round === round);
    const okRows = rows.filter(r => r.n);
    return {
      id, engine: rows[0].engine, mode: rows[0].mode, ua: rows[0].ua,
      round1: { tried: byRound(1).length, results: byRound(1).filter(r => r.outcome === 'results').length, blocked: byRound(1).filter(r => r.outcome === 'blocked').length },
      round2: { tried: byRound(2).length, results: byRound(2).filter(r => r.outcome === 'results').length, blocked: byRound(2).filter(r => r.outcome === 'blocked').length },
      avgResults: okRows.length ? Number((okRows.reduce((s, r) => s + r.n, 0) / okRows.length).toFixed(1)) : 0,
      directRatio: okRows.length ? Number((okRows.reduce((s, r) => s + r.nDirect / r.n, 0) / okRows.length).toFixed(2)) : 0,
      relevance: okRows.length ? Number((okRows.reduce((s, r) => s + r.relevance, 0) / okRows.length).toFixed(2)) : 0,
      medianMs: rows.map(r => r.ms).sort((a, b) => a - b)[Math.floor(rows.length / 2)],
    };
  }),
};
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');
say(`survey done in ${summary.seconds}s; ${records.length} searches`);
process.exit(0);
