// F7-S3 group 6: Bing alone through the dist adapter, recording what #b_results actually contains
// (children tag/class summary and counts) on the same page the parser saw. One Bing request, no Google request.
//   TMPDIR=<short dir> PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node bing_probe.mjs <dist-dir> <query>
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [distArg, query] = process.argv.slice(2);
const dist = path.resolve(distArg);
const cheerio = createRequire(path.join(dist, 'index.js'))('cheerio');
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
const { sharedBrowserPool, CallBudget } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
console.log = () => undefined;
let seen;
const parse = SearchEngine.prototype.parseBingResults;
SearchEngine.prototype.parseBingResults = function (html, pageUrl) {
  const $ = cheerio.load(html);
  const children = $('#b_results').children().map((_i, el) => `${el.tagName}.${($(el).attr('class') ?? '').trim().split(/\s+/).join('.')}`).get();
  const counts = {};
  for (const key of children) counts[key] = (counts[key] ?? 0) + 1;
  seen = {
    page_path: new URL(pageUrl).pathname, page_query_keys: [...new URL(pageUrl).searchParams.keys()],
    page_title: $('title').first().text().slice(0, 200), b_results_children: counts, b_algo_anywhere: $('.b_algo').length,
    h2_links_in_b_results: $('#b_results h2 a').length, b_content: $('#b_content').length,
    visible_text_excerpt: Array.from($('#b_results').text().replace(/\s+/g, ' ').trim()).slice(0, 600).join(''),
  };
  return parse.call(this, html, pageUrl);
};
const engine = new SearchEngine();
const state = { name: 'Bing', attempted: false, attempts: 0, parsedCount: 0, status: 'not_attempted' };
const budget = new CallBudget(60000);
let error = null, batch = [];
try { batch = await engine.tryBingSearch(query, 5, 4000, state, budget); } catch (failure) { error = String(failure?.message ?? failure).split('\n')[0]; }
finally { budget.dispose(); await sharedBrowserPool.closeAll(); }
process.stdout.write(JSON.stringify({ query, http_status: state.httpStatus ?? null, error, parsed: batch.length, titles: batch.map(r => r.title.slice(0, 120)), page: seen }) + '\n');
