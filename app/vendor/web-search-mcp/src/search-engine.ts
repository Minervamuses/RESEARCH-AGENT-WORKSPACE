import * as cheerio from 'cheerio';
import type { Page, Request } from 'playwright';
import { SearchOptions, SearchResult, SearchResultWithMetadata, SearchEngineState, LinkResolution } from './types.js';
import { sanitizeQuery } from './utils.js';
import { RateLimiter } from './rate-limiter.js';
import { BrowserPool, sharedBrowserPool, CallBudget, OPERATION_TIMEOUTS, boundedRead } from './browser-pool.js';

/** FA13: a fixed rule, not semantic detection. Han characters select Taiwan Chinese; all else English. */
export function queryMarket(query: string): { googleHl: string; bingSetlang: string; bingCc: string } {
  return /\p{Script=Han}/u.test(query)
    ? { googleHl: 'zh-TW', bingSetlang: 'zh-Hant', bingCc: 'TW' }
    : { googleHl: 'en', bingSetlang: 'en', bingCc: 'US' };
}

/** Admits one engine's parsed batch; engine methods call it inside their own page lease. */
type Admit = (batch: SearchResult[], page: Page) => Promise<void>;

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
      { method: this.tryGoogleSearch.bind(this), name: 'Google', host: SearchEngine.googleHost },
      { method: this.tryBingSearch.bind(this), name: 'Bing', host: SearchEngine.bingHost },
    ];
    const engines: SearchEngineState[] = approaches.map(({ name }) => ({
      name, attempted: false, attempts: 0, parsedCount: 0, status: 'not_attempted',
    }));
    const results: SearchResult[] = [];
    const byUrl = new Map<string, SearchResult>();
    let running: Promise<void> | undefined;
    const work = async () => {
      for (const [index, approach] of approaches.entries()) {
        const state = engines[index];
        if (results.length >= numResults) { state.status = 'strategy_stopped'; continue; }
        let timeout: number;
        try { timeout = budget.timeout(OPERATION_TIMEOUTS.searchRequest); } catch (error) {
          this.notAttempted(state, error, 'deadline');
          continue;
        }
        // A method abandoned at the call deadline may still run; it must not change results afterwards.
        let open = true;
        const admit: Admit = (batch, page) => this.admitBatch(batch, page, approach, {
          results, byUrl, numResults, budget, open: () => open,
        });
        try {
          const batch = await budget.wait(approach.method(sanitizeQuery(query), numResults, timeout, state, budget, admit));
          state.parsedCount = batch.length;
          state.status = batch.length ? 'completed' : 'zero_parsed';
        } catch (error) {
          // A lease that never started only waited for a page slot: not an engine failure.
          if (!state.attempts && budget.signal.aborted && error === budget.signal.reason) {
            this.notAttempted(state, error, 'queue_expired');
          } else {
            state.status = 'error';
            state.error = error instanceof Error ? error.message : String(error);
          }
        } finally { open = false; }
      }
    };
    let expiredAtEntry = false;
    try { budget.remaining(); } catch { expiredAtEntry = true; }
    try {
      await this.rateLimiter.execute(() => { running = work(); return running; }, budget);
    } catch (error) {
      // A running loop settles its own facts; otherwise no engine started at all.
      if (running) await running.catch(() => undefined);
      else for (const state of engines) this.notAttempted(state, error, expiredAtEntry ? 'deadline' : 'queue_expired');
    } finally { if (!options.budget) budget.dispose(); }
    return { results, engines };
  }

  /** FA07: why an engine never started; the original message stays in error. */
  private notAttempted(state: SearchEngineState, error: unknown, otherwise: 'deadline' | 'queue_expired'): void {
    const message = error instanceof Error ? error.message : String(error);
    state.status = 'not_attempted';
    state.reason = (error as any)?.code === 'ERR_CANCELED' ? 'cancelled'
      : /^Rate limit exceeded/.test(message) ? 'rate_limited' : otherwise;
    state.error = message;
  }

  /**
   * Admits a batch in order: candidates fill to the limit at once (so a call deadline never loses
   * them), then engine redirect wrappers are resolved on the engine's own page, one by one (FA14).
   * A wrapper that resolves to a known URL merges its provenance and lets the next item in.
   */
  private async admitBatch(
    batch: SearchResult[], page: Page, engine: { name: string; host: string },
    call: { results: SearchResult[]; byUrl: Map<string, SearchResult>; numResults: number; budget: CallBudget; open: () => boolean },
  ): Promise<void> {
    const { results, byUrl, numResults, budget, open } = call;
    const referer = page.url();
    const queue: SearchResult[] = [];
    for (const item of batch) {
      try {
        const url = new URL(item.url);
        if (['http:', 'https:'].includes(url.protocol)) queue.push({ ...item, url: url.href });
      } catch { /* Not a navigable result address. */ }
    }
    const isWrapper = (url: string) => new URL(url).host === engine.host;
    const merge = (candidate: SearchResult, previous: SearchResult) => {
      for (const name of candidate.sourceEngines!) if (!previous.sourceEngines!.includes(name)) previous.sourceEngines!.push(name);
    };
    const wrappers: SearchResult[] = [];
    const fill = () => {
      while (results.length < numResults && queue.length) {
        const item = queue.shift()!;
        const candidate: SearchResult = { ...item, observedUrl: item.observedUrl ?? item.url, sourceEngines: [engine.name] };
        const previous = byUrl.get(candidate.url);
        if (previous) { merge(candidate, previous); continue; }
        if (isWrapper(candidate.url)) {
          candidate.resolution = { wrapperUrl: candidate.url, outcome: 'not_started', reason: 'call deadline reached before resolution started' };
          wrappers.push(candidate);
        }
        results.push(candidate);
        byUrl.set(candidate.url, candidate);
      }
    };
    fill();
    for (let index = 0; index < wrappers.length && open(); index++) {
      const candidate = wrappers[index];
      let capMs: number;
      try { capMs = budget.timeout(OPERATION_TIMEOUTS.linkResolve); } catch { break; }
      const wrapperUrl = candidate.url;
      candidate.resolution = { wrapperUrl, outcome: 'timeout', reason: 'call deadline reached during resolution' };
      const found = await this.resolveWrapper(page, wrapperUrl, engine.host, referer, capMs);
      if (!open()) return;
      candidate.resolution = { wrapperUrl, ...found.resolution };
      if (!found.url) continue;
      const resolved = new URL(found.url).href;
      byUrl.delete(wrapperUrl);
      const previous = byUrl.get(resolved);
      if (previous) {
        merge(candidate, previous);
        results.splice(results.indexOf(candidate), 1);
        fill();
      } else {
        candidate.url = resolved;
        byUrl.set(resolved, candidate);
      }
    }
    // Items past the limit only add provenance when they are already known; wrappers are not followed.
    for (const item of queue) {
      const previous = byUrl.get(item.url);
      if (previous && !previous.sourceEngines!.includes(engine.name)) previous.sourceEngines!.push(engine.name);
    }
  }

  /**
   * Follows one wrapper on the search page itself, referred by the search page. The first main-frame
   * navigation request whose host is not the engine host is the destination; its response is not awaited.
   */
  private async resolveWrapper(
    page: Page, wrapperUrl: string, host: string, referer: string, capMs: number,
  ): Promise<{ url?: string; resolution: Omit<LinkResolution, 'wrapperUrl'> }> {
    const begin = performance.now();
    const ms = () => Math.round(performance.now() - begin);
    let onRequest: (request: Request) => void = () => undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let committed = false;
    try {
      const destination = new Promise<string>(resolve => {
        onRequest = request => {
          try {
            if (request.isNavigationRequest() && request.frame() === page.mainFrame()
              && new URL(request.url()).host !== host) resolve(request.url());
          } catch { /* Requests without a frame or URL are not navigations of this page. */ }
        };
        page.on('request', onRequest);
      });
      const failure = new Promise<unknown>(resolve => {
        // The interrupted or late navigation promise is always handled here.
        page.goto(wrapperUrl, { referer, waitUntil: 'commit', timeout: capMs }).then(
          () => { committed = true; },
          error => { if ((error as any)?.name !== 'TimeoutError') resolve(error); },
        );
      });
      const expired = new Promise<void>(resolve => { timer = setTimeout(resolve, capMs); });
      const outcome = await Promise.race([
        destination.then(url => ({ url })), failure.then(error => ({ error })), expired.then(() => ({})),
      ]);
      if ('url' in outcome) return { url: outcome.url, resolution: { outcome: 'resolved', ms: ms() } };
      if ('error' in outcome) {
        const message = outcome.error instanceof Error ? outcome.error.message : String(outcome.error);
        return { resolution: { outcome: 'failed', ms: ms(), reason: message.split('\n')[0].replace(/\x1b\[[0-9;]*m/g, '').trim() } };
      }
      return committed
        ? { resolution: { outcome: 'stayed_on_engine_host', ms: ms(), reason: `the redirect page responded but no navigation left ${host} within ${capMs} ms` } }
        : { resolution: { outcome: 'timeout', ms: ms(), reason: `the redirect page did not respond within ${capMs} ms` } };
    } finally {
      page.off('request', onRequest);
      if (timer) clearTimeout(timer);
    }
  }

  private async tryGoogleSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
    admit?: Admit,
  ): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      const url = new URL(SearchEngine.googleSearchUrl);
      url.searchParams.set('q', query);
      url.searchParams.set('hl', queryMarket(query).googleHl);
      url.searchParams.set('num', String(numResults));
      const response = await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: budget.timeout(timeout) });
      const status = response?.status();
      if (state) state.httpStatus = status;
      // Observed HTTP facts only: no retry, no workaround, no challenge-page vocabulary.
      if (status !== undefined && status >= 400) throw new Error(`Google returned HTTP ${status}`);
      const finalPath = new URL(page.url()).pathname;
      if (finalPath.startsWith('/sorry/')) {
        if (state) state.finalPath = finalPath;
        throw new Error(`Google redirected to ${finalPath} (HTTP ${status ?? 'unknown'})`);
      }
      await this.waitForResults(page, '#search a h3, #rso a h3', budget);
      const batch = this.parseGoogleResults(await boundedRead(page.content(), budget, 'Google results page.content()'), page.url());
      await admit?.(batch, page);
      return batch;
    }, budget, () => this.started(state));
  }

  private started(state?: SearchEngineState): void {
    if (state) { state.attempted = true; state.attempts++; }
  }

  private async tryBingSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
    admit?: Admit,
  ): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      const market = queryMarket(query);
      const url = new URL(SearchEngine.bingSearchUrl);
      url.searchParams.set('q', query);
      url.searchParams.set('count', String(numResults));
      url.searchParams.set('setlang', market.bingSetlang);
      url.searchParams.set('cc', market.bingCc);
      const response = await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: budget.timeout(timeout) });
      const status = response?.status();
      if (state) state.httpStatus = status;
      if (status !== undefined && status >= 400) throw new Error(`Bing returned HTTP ${status}`);
      await this.waitForResults(page, '#b_results > li.b_algo', budget);
      const batch = this.parseBingResults(await boundedRead(page.content(), budget, 'Bing results page.content()'), page.url());
      await admit?.(batch, page);
      return batch;
    }, budget, () => this.started(state));
  }

  private async waitForResults(page: Page, selector: string, budget: CallBudget): Promise<void> {
    await page.waitForSelector(selector, {
      timeout: budget.timeout(OPERATION_TIMEOUTS.searchSelector),
    }).catch(() => undefined);
    budget.remaining();
  }

  /** Every result link on the page; admission applies the limit, so duplicates can be replaced. */
  private parseGoogleResults(html: string, pageUrl = SearchEngine.googleSearchUrl): SearchResult[] {
    const $ = cheerio.load(html);
    const baseUrl = this.searchPageBase($, pageUrl);
    const root = $('#search').length ? $('#search').first() : $('#rso').first();
    const anchors = root.find('a:has(h3)');
    const results: SearchResult[] = [];
    anchors.each((_index, anchor) => {
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

  private parseBingResults(html: string, pageUrl = SearchEngine.bingSearchUrl): SearchResult[] {
    const $ = cheerio.load(html);
    const baseUrl = this.searchPageBase($, pageUrl);
    // Only organic results; sidebar modules are never counted as results.
    const items = $('#b_results > li.b_algo');
    const results: SearchResult[] = [];
    items.each((_index, element) => {
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
