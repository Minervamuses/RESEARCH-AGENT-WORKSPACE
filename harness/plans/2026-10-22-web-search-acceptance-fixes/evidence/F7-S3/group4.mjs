// F7-S3 group 4: each engine on its own through the dist adapter (not the full Python chain).
//   TMPDIR=<short dir> PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright node group4.mjs <dist-dir> <query>
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [distArg, query] = process.argv.slice(2);
const dist = path.resolve(distArg);
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
const { sharedBrowserPool, CallBudget } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);
process.argv[1] = path.join(dist, 'index.js');
const { observe } = await import(pathToFileURL(path.join(path.dirname(new URL(import.meta.url).pathname), 'observe.mjs')).href);
const structure = [];
observe(SearchEngine, record => structure.push(record));
console.log = () => undefined;
const engine = new SearchEngine();
const out = { query, engines: [] };
try {
  for (const [method, name, host] of [['tryGoogleSearch', 'Google', SearchEngine.googleHost], ['tryBingSearch', 'Bing', SearchEngine.bingHost]]) {
    const state = { name, attempted: false, attempts: 0, parsedCount: 0, status: 'not_attempted' };
    const results = [], byUrl = new Map();
    const budget = new CallBudget(60000);
    const begin = performance.now();
    let error = null, batch = [];
    try {
      batch = await engine[method](query, 5, 4000, state, budget, (items, page) =>
        engine.admitBatch(items, page, { name, host }, { results, byUrl, numResults: 5, budget, open: () => true }));
    } catch (failure) { error = failure instanceof Error ? failure.message.split('\n')[0] : String(failure); }
    budget.dispose();
    out.engines.push({
      name, ms: Math.round(performance.now() - begin), http_status: state.httpStatus ?? null, final_path: state.finalPath ?? null,
      attempts: state.attempts, error, parsed: batch.length,
      results: results.map(r => ({ title: Array.from(r.title).slice(0, 200).join(''), url: r.url, snippet: Array.from(r.description).slice(0, 300).join(''),
        observed: Array.from(r.observedUrl ?? '').slice(0, 120).join(''), resolution: r.resolution ? { outcome: r.resolution.outcome, ms: r.resolution.ms ?? null, reason: r.resolution.reason ?? null, wrapper_host: new URL(r.resolution.wrapperUrl).host } : null })),
    });
  }
} finally { await sharedBrowserPool.closeAll(); }
out.structure = structure;
process.stdout.write(JSON.stringify(out) + '\n');
