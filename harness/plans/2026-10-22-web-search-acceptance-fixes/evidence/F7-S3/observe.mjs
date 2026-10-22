// F7-S3 observe-only preload: node --import observe.mjs?log=<file> <dist>/index.js
// It wraps the two parsers to record structure counts of the same result page the engine parsed, so no
// extra request is sent. Behaviour is unchanged. Excerpts keep only tags with href/class, at most 2000 code points.
import { appendFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const log = new URL(import.meta.url).searchParams.get('log');
const dist = path.dirname(path.resolve(process.argv[1]));
const cheerio = createRequire(path.join(dist, 'index.js'))('cheerio');
const { SearchEngine } = await import(pathToFileURL(path.join(dist, 'search-engine.js')).href);
export function observe(engineClass, write) {
  const skeleton = node => {
    const $ = cheerio.load(node ?? '');
    $('script, style, noscript, template, svg, img').remove();
    $('*').each((_i, element) => {
      for (const name of Object.keys(element.attribs ?? {})) if (!['href', 'class'].includes(name)) $(element).removeAttr(name);
    });
    return Array.from(($('body').html() ?? '').replace(/\s+/g, ' ').trim()).slice(0, 2000).join('');
  };
  for (const [method, engine, root, item, block] of [
    ['parseGoogleResults', 'Google', $ => ($('#search').length ? $('#search') : $('#rso')), $r => $r.find('a:has(h3)'), $ => $('#rso').children().first()],
    ['parseBingResults', 'Bing', $ => $('#b_results'), $r => $r.children('li.b_algo'), $ => $('#b_results > li.b_algo').first()],
  ]) {
    const original = engineClass.prototype[method];
    engineClass.prototype[method] = function (html, pageUrl) {
      const parsed = original.call(this, html, pageUrl);
      const $ = cheerio.load(html);
      const $root = root($);
      write({
        engine, at: new Date().toISOString(), page_path: new URL(pageUrl).pathname, page_query_keys: [...new URL(pageUrl).searchParams.keys()],
        has_result_root: $root.length > 0, structure_count: $root.length ? item($root).length : 0, parsed: parsed.length,
        page_title: $('title').first().text().slice(0, 200), first_block_skeleton: skeleton($.html(block($))),
      });
      return parsed;
    };
  }
}
if (log) observe(SearchEngine, record => appendFileSync(log, `${JSON.stringify(record)}\n`));
