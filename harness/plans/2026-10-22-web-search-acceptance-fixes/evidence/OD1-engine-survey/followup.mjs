// Follow-up diagnosis for OD1 (6 paced public requests): what do the Bing and Google pages actually contain?
// Usage: T=$(mktemp -d /tmp/sv.XXXX); TMPDIR=$T PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node followup.mjs <output-dir>
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

const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'] });
const major = browser.version().split('.')[0];
const UA = `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
const engine = new SearchEngine();
const report = [];

async function load(url, ua, waitSelector) {
  const context = await browser.newContext(ua ? { userAgent: UA } : {});
  const page = await context.newPage();
  try {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    if (waitSelector) await page.waitForSelector(waitSelector, { timeout: 5000 }).catch(() => undefined);
    return { status: response?.status(), finalUrl: page.url(), title: await page.title(), html: await page.content() };
  } finally { await context.close(); }
}

const bingCases = [
  { label: 'bing default, default UA', q: 'how does photosynthesis work', params: '', ua: false },
  { label: 'bing setlang=en cc=US, default UA', q: 'how does photosynthesis work', params: '&setlang=en&cc=US', ua: false },
  { label: 'bing setlang=en cc=US, normal UA', q: 'python asyncio cancel task', params: '&setlang=en&cc=US', ua: true },
  { label: 'bing default, normal UA (zh query)', q: '機器學習 過擬合 解決方法', params: '', ua: true },
];
for (const c of bingCases) {
  const url = `https://www.bing.com/search?q=${encodeURIComponent(c.q)}&count=10${c.params}`;
  const page = await load(url, c.ua, '#b_results .b_algo');
  const $ = cheerio.load(page.html);
  const organic = $('#b_results > li.b_algo').map((_i, li) => short($(li).find('h2').first().text(), 70)).get();
  const parsed = engine.parseBingResults(page.html, 10, page.finalUrl).map(r => short(r.title, 70));
  const record = {
    kind: 'bing', label: c.label, query: c.q, status: page.status, title: short(page.title, 80),
    organicCount: organic.length, organicTitles: organic.slice(0, 4), parsedCount: parsed.length, parsedTitles: parsed.slice(0, 4),
    resultsListChildren: $('#b_results > li').length, hasBResults: $('#b_results').length > 0,
  };
  report.push(record);
  say(JSON.stringify(record));
  await sleep(6000);
}

const googleCases = [
  { q: 'python asyncio cancel task', hl: 'en' },
  { q: '機器學習 過擬合 解決方法', hl: 'zh-TW' },
];
for (const c of googleCases) {
  const page = await load(`https://www.google.com/search?q=${encodeURIComponent(c.q)}&hl=${c.hl}&num=10`, true, 'a h3');
  const $ = cheerio.load(page.html);
  const anchors = $('a:has(h3)').map((_i, a) => ({ href: short($(a).attr('href'), 90), h3: short($(a).find('h3').text(), 60) })).get();
  const record = {
    kind: 'google', query: c.q, status: page.status, finalPath: new URL(page.finalUrl).pathname, title: short(page.title, 80),
    h3Count: $('h3').length, resultAnchors: anchors.length, sampleAnchors: anchors.slice(0, 4),
    hrefKinds: [...new Set(anchors.map(a => a.href.startsWith('/url?') ? 'google /url wrapper' : a.href.startsWith('http') ? 'direct' : 'other'))],
  };
  report.push(record);
  say(JSON.stringify(record));
  await sleep(8000);
}
await browser.close();
fs.writeFileSync(path.join(OUT, 'followup.json'), JSON.stringify({ at: new Date().toISOString(), chrome: browser.version?.() ?? major, report }, null, 2) + '\n');
say('followup done');
