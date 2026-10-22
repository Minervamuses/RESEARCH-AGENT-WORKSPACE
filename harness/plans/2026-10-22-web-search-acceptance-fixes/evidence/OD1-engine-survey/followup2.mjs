// Second follow-up for OD1: Google by browser mode with a normal UA, Google /goto resolution by real
// navigation, and Bing with a market matched to the query language. About 12 Google + 6 Bing searches, paced.
// Usage: T=$(mktemp -d /tmp/sv.XXXX); TMPDIR=$T PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node followup2.mjs <output-dir>
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const VENDOR = '/home/minervamuses/research-agent-workspace/app/vendor/web-search-mcp';
const OUT = path.resolve(process.argv[2] ?? '.');
const cheerio = createRequire(path.join(VENDOR, 'package.json'))('cheerio');
const { chromium } = await import(path.join(VENDOR, 'node_modules/playwright/index.mjs'));
const { SearchEngine } = await import(path.join(VENDOR, 'dist/search-engine.js'));
console.log = console.error = () => {};
const say = text => process.stdout.write(text + '\n');
const short = (t, n) => (t ?? '').replace(/\s+/g, ' ').trim().slice(0, n);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const host = url => { try { return new URL(url).hostname; } catch { return 'invalid'; } };

const QUERIES = [
  { q: 'python asyncio cancel task', lang: 'en', terms: ['asyncio', 'cancel'] },
  { q: '機器學習 過擬合 解決方法', lang: 'zh', terms: ['過擬合', '過度擬合', 'overfitting'] },
  { q: '台灣 颱風 最新消息', lang: 'zh', terms: ['颱風'] },
  { q: 'how does photosynthesis work', lang: 'en', terms: ['photosynthesis', '光合作用'] },
  { q: 'Playwright headless detection', lang: 'en', terms: ['playwright', 'headless'] },
  { q: '台北 捷運 路線圖', lang: 'zh', terms: ['捷運'] },
];
const ARGS = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'];
const browsers = {};
async function browserFor(mode) {
  if (!browsers[mode]) {
    const channel = { full_chromium: 'chromium', system_chrome: 'chrome' }[mode];
    browsers[mode] = await chromium.launch({ headless: true, args: ARGS, ...(channel ? { channel } : {}) });
  }
  return browsers[mode];
}
const uaFor = browser => `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${browser.version().split('.')[0]}.0.0.0 Safari/537.36`;
const relevance = (items, query) => items.length
  ? Number((items.filter(i => query.terms.some(t => i.title.toLowerCase().includes(t.toLowerCase()))).length / items.length).toFixed(2)) : 0;

const results = [];
const record = r => { results.push(r); say(JSON.stringify(r)); };

async function google(mode, query, resolveLinks = 0) {
  const browser = await browserFor(mode);
  const context = await browser.newContext({ userAgent: uaFor(browser) });
  const page = await context.newPage();
  const started = Date.now();
  try {
    const url = `https://www.google.com/search?q=${encodeURIComponent(query.q)}&hl=${query.lang === 'zh' ? 'zh-TW' : 'en'}&num=10`;
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForSelector('a h3', { timeout: 5000 }).catch(() => undefined);
    const $ = cheerio.load(await page.content());
    const items = $('a:has(h3)').map((_i, a) => ({ title: short($(a).find('h3').first().text(), 70), href: $(a).attr('href') ?? '' })).get();
    const blocked = page.url().includes('/sorry/') || (response?.status() ?? 0) >= 400;
    const out = {
      kind: 'google', mode, query: query.q, status: response?.status(), blocked, ms: Date.now() - started, n: items.length,
      wrapped: items.filter(i => !/^https?:/.test(i.href)).length, relevance: relevance(items, query),
      titles: items.slice(0, 3).map(i => i.title),
    };
    if (resolveLinks && items.length) {
      out.resolved = [];
      for (const item of items.slice(0, resolveLinks)) {
        const t0 = Date.now();
        const tab = await context.newPage();
        try {
          await tab.goto(new URL(item.href, 'https://www.google.com/').href, { waitUntil: 'domcontentloaded', timeout: 15000, referer: url });
          await tab.waitForURL(u => !u.hostname.endsWith('google.com'), { timeout: 8000 }).catch(() => undefined);
          out.resolved.push({ title: item.title, finalHost: host(tab.url()), ms: Date.now() - t0 });
        } catch (e) { out.resolved.push({ title: item.title, error: short(e.message, 80), ms: Date.now() - t0 }); }
        finally { await tab.close(); }
        await sleep(2000);
      }
    }
    record(out);
  } catch (e) { record({ kind: 'google', mode, query: query.q, error: short(e.message, 120), ms: Date.now() - started }); }
  finally { await context.close(); }
}

async function bing(query) {
  const browser = await browserFor('headless_shell');
  const context = await browser.newContext({ userAgent: uaFor(browser) });
  const page = await context.newPage();
  const started = Date.now();
  try {
    const market = query.lang === 'zh' ? '&setlang=zh-Hant&cc=TW' : '&setlang=en&cc=US';
    const response = await page.goto(`https://www.bing.com/search?q=${encodeURIComponent(query.q)}&count=10${market}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForSelector('#b_results .b_algo', { timeout: 5000 }).catch(() => undefined);
    const html = await page.content();
    const $ = cheerio.load(html);
    const organic = $('#b_results > li.b_algo').length;
    const items = new SearchEngine().parseBingResults(html, 10, page.url());
    record({
      kind: 'bing', mode: 'headless_shell+normal UA', market: market.slice(1), query: query.q, status: response?.status(), ms: Date.now() - started,
      organic, n: items.length, relevance: relevance(items, query), titles: items.slice(0, 3).map(i => short(i.title, 70)),
    });
  } catch (e) { record({ kind: 'bing', query: query.q, error: short(e.message, 120), ms: Date.now() - started }); }
  finally { await context.close(); }
}

const t0 = Date.now();
// Interleave so Google sees one request roughly every 12-15 s.
const plan = [
  () => google('headless_shell', QUERIES[0]), () => bing(QUERIES[0]),
  () => google('full_chromium', QUERIES[1]), () => bing(QUERIES[1]),
  () => google('system_chrome', QUERIES[2]), () => bing(QUERIES[2]),
  () => google('headless_shell', QUERIES[3]), () => bing(QUERIES[3]),
  () => google('full_chromium', QUERIES[4]), () => bing(QUERIES[4]),
  () => google('system_chrome', QUERIES[5]), () => bing(QUERIES[5]),
  () => google('headless_shell', QUERIES[1]),
  () => google('full_chromium', QUERIES[2]),
  () => google('system_chrome', QUERIES[0]),
  () => google('headless_shell', QUERIES[4], 3),
];
for (const step of plan) { await step(); await sleep(6500); }
for (const b of Object.values(browsers)) await b.close();
fs.writeFileSync(path.join(OUT, 'followup2.json'), JSON.stringify({ at: new Date().toISOString(), seconds: Math.round((Date.now() - t0) / 1000), results }, null, 2) + '\n');
say(`followup2 done in ${Math.round((Date.now() - t0) / 1000)}s`);
