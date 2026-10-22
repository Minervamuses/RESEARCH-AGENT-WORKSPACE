import * as cheerio from 'cheerio';
import type { Page } from 'playwright';
import { SearchOptions, SearchResult, SearchResultWithMetadata, SearchEngineState } from './types.js';
import { sanitizeQuery } from './utils.js';
import { RateLimiter } from './rate-limiter.js';
import { BrowserPool, sharedBrowserPool, CallBudget, OPERATION_TIMEOUTS } from './browser-pool.js';

/** FA13: a fixed rule, not semantic detection. Han characters select Taiwan Chinese; all else English. */
export function queryMarket(query: string): { googleHl: string; bingSetlang: string; bingCc: string } {
  return /\p{Script=Han}/u.test(query)
    ? { googleHl: 'zh-TW', bingSetlang: 'zh-Hant', bingCc: 'TW' }
    : { googleHl: 'en', bingSetlang: 'en', bingCc: 'US' };
}

export class SearchEngine {
  // Search addresses are overridable static members (tests, local fake engines), not environment settings.
  static googleSearchUrl = 'https://www.google.com/search';
  static googleHost = 'www.google.com';
  static bingSearchUrl = 'https://www.bing.com/search';
  static bingHost = 'www.bing.com';

  private readonly rateLimiter: RateLimiter;
  private browserPool: BrowserPool;

  constructor(pool: BrowserPool = sharedBrowserPool) {
    this.rateLimiter = new RateLimiter(10); // 10 requests per minute
    this.browserPool = pool;
  }

  async search(options: SearchOptions & { budget?: CallBudget }): Promise<SearchResultWithMetadata> {
    const { query, numResults = 5 } = options;
    const budget = options.budget ?? new CallBudget(options.timeout);
    const approaches = [
      { method: this.tryGoogleSearch.bind(this), name: 'Google' },
      { method: this.tryBingSearch.bind(this), name: 'Bing' },
    ];
    const engines: SearchEngineState[] = approaches.map(({ name }) => ({
      name, attempted: false, attempts: 0, parsedCount: 0, status: 'strategy_stopped',
    }));
    const results: SearchResult[] = [];
    const byUrl = new Map<string, SearchResult>();
    let running: Promise<void> | undefined;
    const work = async () => {
      for (const [index, approach] of approaches.entries()) {
        const state = engines[index];
        if (results.length >= numResults) continue;
        if (budget.signal.aborted) { state.error = String(budget.signal.reason); continue; }
        state.attempted = true;
        try {
          const batch = await budget.wait(approach.method(
            sanitizeQuery(query), numResults, budget.timeout(OPERATION_TIMEOUTS.searchRequest), state, budget,
          ));
          state.parsedCount = batch.length;
          state.status = batch.length ? 'completed' : 'zero_parsed';
          for (const item of batch) {
            let url: URL;
            try {
              url = new URL(item.url);
              if (!['http:', 'https:'].includes(url.protocol)) continue;
            } catch { continue; }
            const previous = byUrl.get(url.href);
            if (previous) {
              if (!previous.sourceEngines!.includes(approach.name)) previous.sourceEngines!.push(approach.name);
              continue;
            }
            if (results.length >= numResults) continue;
            const candidate: SearchResult = {
              ...item, url: url.href, observedUrl: item.observedUrl ?? item.url,
              sourceEngines: [approach.name],
            };
            results.push(candidate);
            byUrl.set(url.href, candidate);
          }
        } catch (error) {
          state.status = 'error';
          state.error = error instanceof Error ? error.message : String(error);
        } finally { state.attempts = Math.max(1, state.attempts); }
      }
    };
    try {
      await this.rateLimiter.execute(() => { running = work(); return running; }, budget);
    } catch (error) {
      // A queued call can expire before starting. A running loop settles its facts before return.
      if (running) await running.catch(() => undefined);
      for (const state of engines) {
        if (!state.attempted) state.error = error instanceof Error ? error.message : String(error);
      }
    } finally { if (!options.budget) budget.dispose(); }
    return { results, engines };
  }

  private async tryGoogleSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
  ): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      if (state) state.attempts = 1;
      const url = new URL(SearchEngine.googleSearchUrl);
      url.searchParams.set('q', query);
      url.searchParams.set('hl', queryMarket(query).googleHl);
      url.searchParams.set('num', String(numResults));
      const response = await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: budget.timeout(timeout) });
      const status = response?.status();
      // Observed HTTP facts only: no retry, no workaround, no challenge-page vocabulary.
      if (status !== undefined && status >= 400) throw new Error(`Google returned HTTP ${status}`);
      const finalPath = new URL(page.url()).pathname;
      if (finalPath.startsWith('/sorry/')) throw new Error(`Google redirected to ${finalPath} (HTTP ${status ?? 'unknown'})`);
      await this.waitForResults(page, '#search a h3, #rso a h3', budget);
      return this.parseGoogleResults(await page.content(), numResults, page.url());
    }, budget);
  }

  private async tryBingSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
  ): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      if (state) state.attempts = 1;
      const market = queryMarket(query);
      const url = new URL(SearchEngine.bingSearchUrl);
      url.searchParams.set('q', query);
      url.searchParams.set('count', String(numResults));
      url.searchParams.set('setlang', market.bingSetlang);
      url.searchParams.set('cc', market.bingCc);
      const response = await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: budget.timeout(timeout) });
      const status = response?.status();
      if (status !== undefined && status >= 400) throw new Error(`Bing returned HTTP ${status}`);
      await this.waitForResults(page, '#b_results > li.b_algo', budget);
      return this.parseBingResults(await page.content(), numResults, page.url());
    }, budget);
  }

  private async waitForResults(page: Page, selector: string, budget: CallBudget): Promise<void> {
    await page.waitForSelector(selector, {
      timeout: budget.timeout(OPERATION_TIMEOUTS.searchSelector),
    }).catch(() => undefined);
    budget.remaining();
  }

  private parseGoogleResults(html: string, maxResults: number, pageUrl = SearchEngine.googleSearchUrl): SearchResult[] {
    const $ = cheerio.load(html);
    const baseUrl = this.searchPageBase($, pageUrl);
    const root = $('#search').length ? $('#search').first() : $('#rso').first();
    const anchors = root.find('a:has(h3)');
    const results: SearchResult[] = [];
    anchors.each((_index, anchor) => {
      if (results.length >= maxResults) return false;
      const href = $(anchor).attr('href');
      if (!href || !this.isValidSearchUrl(href, baseUrl)) return;
      // The result block is the largest ancestor holding only this result link.
      let block = $(anchor);
      while (block.parent().length && !block.parent().is(root) && block.parent().find('a:has(h3)').length === 1) {
        block = block.parent();
      }
      results.push({
        title: $(anchor).find('h3').first().text().trim(),
        // Google's wrapper href is relative (/goto?url=...); resolve it against the actual page (R04).
        url: new URL(href, baseUrl).href,
        observedUrl: href,
        description: block.find('[data-sncf], .VwiC3b').first().text().trim(),
      });
    });
    console.error(`[SearchEngine] Google: ${results.length} results from ${anchors.length} result links`);
    return results;
  }

  private parseBingResults(html: string, maxResults: number, pageUrl = SearchEngine.bingSearchUrl): SearchResult[] {
    const $ = cheerio.load(html);
    const baseUrl = this.searchPageBase($, pageUrl);
    // Only organic results; sidebar modules are never counted as results.
    const items = $('#b_results > li.b_algo');
    const results: SearchResult[] = [];
    items.each((_index, element) => {
      if (results.length >= maxResults) return false;
      const $element = $(element);
      const link = $element.find('h2 a, .b_title a, a[data-seid]').first();
      const href = link.attr('href');
      if (!href || !this.isValidSearchUrl(href, baseUrl)) return;
      let snippet = '';
      for (const selector of ['.b_caption p', '.b_snippet', '.b_descript', '.b_caption', '.b_excerpt', 'p']) {
        snippet = $element.find(selector).first().text().trim();
        if (snippet) break;
      }
      results.push({ title: link.text().trim(), url: new URL(href, baseUrl).href, observedUrl: href, description: snippet });
    });
    console.error(`[SearchEngine] Bing: ${results.length} results from ${items.length} organic items`);
    return results;
  }

  private searchPageBase($: cheerio.CheerioAPI, finalUrl: string): string {
    const href = $('base[href]').first().attr('href');
    try {
      const base = new URL(href ?? finalUrl, finalUrl);
      return ['http:', 'https:'].includes(base.protocol) ? base.href : finalUrl;
    } catch { return finalUrl; }
  }

  private isValidSearchUrl(url: string, baseUrl: string): boolean {
    try {
      return ['http:', 'https:'].includes(new URL(url, baseUrl).protocol);
    } catch { return false; }
  }
}
