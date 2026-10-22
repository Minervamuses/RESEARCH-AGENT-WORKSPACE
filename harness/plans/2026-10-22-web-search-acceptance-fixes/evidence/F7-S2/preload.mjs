// F7-S2 test-only preload, loaded by the product's custom command: node --import <this file URL>?<query> <dist>/index.js
// web_search only receives allowlisted settings, so this preload is configured by its own URL query string:
//   mode=stub     both engine methods return `count` direct candidates at <base>/slow/<n>
//   mode=engines  the real Google and Bing methods run against fake engine pages: google=<url>, bing=<url>, host=<host>
//   linkResolve=<ms>  shortens the link resolution cap (engines mode)
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const query = new URL(import.meta.url).searchParams;
const dist = path.dirname(path.resolve(process.argv[1]));
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
const { OPERATION_TIMEOUTS } = await import(pathToFileURL(path.join(dist, 'browser-pool.js')).href);

if (query.get('mode') === 'stub') {
  const base = query.get('base');
  const count = Number(query.get('count') ?? 10);
  for (const [method, ids] of [['tryGoogleSearch', Array.from({ length: count }, (_v, i) => i + 1)], ['tryBingSearch', []]]) {
    SearchEngine.prototype[method] = async function (_query, _n, _timeout, state, _budget, admit) {
      state.attempted = true;
      state.attempts++;
      const batch = ids.map(id => ({ title: `Stub ${id}`, url: `${base}/slow/${id}`, description: `stub snippet ${id}` }));
      await admit(batch, { url: () => `${base}/search` });
      return batch;
    };
  }
}
if (query.get('mode') === 'engines') {
  SearchEngine.googleSearchUrl = query.get('google');
  SearchEngine.bingSearchUrl = query.get('bing');
  SearchEngine.googleHost = query.get('host');
  SearchEngine.bingHost = query.get('host');
  if (query.get('linkResolve')) OPERATION_TIMEOUTS.linkResolve = Number(query.get('linkResolve'));
}
