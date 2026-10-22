import axios from 'axios';
import * as cheerio from 'cheerio';
import { SearchOptions, SearchResult, SearchResultWithMetadata, SearchEngineState } from './types.js';
import { sanitizeQuery } from './utils.js';
import { RateLimiter } from './rate-limiter.js';
import { BrowserPool, sharedBrowserPool, CallBudget, OPERATION_TIMEOUTS } from './browser-pool.js';

export class SearchEngine {
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
      { method: this.tryBrowserBingSearch.bind(this), name: 'Browser Bing' },
      { method: this.tryDuckDuckGoSearch.bind(this), name: 'Axios DuckDuckGo' },
      { method: this.tryBrowserBraveSearch.bind(this), name: 'Browser Brave' },
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

  private async tryBrowserBraveSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
  ): Promise<SearchResult[]> {
    for (let attempt = 1; attempt <= 2; attempt++) {
      budget.remaining();
      try {
        return await this.browserPool.withPage(async page => {
          budget.remaining();
          if (state) state.attempts = attempt;
          const response = await page.goto(`https://search.brave.com/search?q=${encodeURIComponent(query)}&source=web`, {
            waitUntil: 'domcontentloaded', timeout: budget.timeout(timeout),
          });
          const status = response?.status();
          if (status !== undefined && status >= 400) {
            throw Object.assign(new Error(`Brave returned HTTP ${status}`), { braveBlocked: true });
          }
          await page.waitForSelector('[data-type="web"]', {
            timeout: budget.timeout(OPERATION_TIMEOUTS.searchSelector),
          }).catch(() => undefined);
          budget.remaining();
          return this.parseBraveResults(await page.content(), numResults, page.url());
        }, budget);
      } catch (error) {
        const err = error as any;
        if (attempt === 2 || budget.signal.aborted || err.braveBlocked
          || !['TimeoutError'].includes(err.name) && !['ECONNRESET', 'ETIMEDOUT'].includes(err.code)) throw error;
      }
    }
    return [];
  }

  private async tryBrowserBingSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
  ): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      if (state) state.attempts = 1;
      try {
        return await this.tryEnhancedBingSearch(page, query, numResults, budget);
      } catch (error) {
        budget.remaining();
        if (state) state.attempts = 2;
        return this.tryDirectBingSearch(page, query, numResults, budget);
      }
    }, budget);
  }

  private async tryEnhancedBingSearch(page: any, query: string, numResults: number, budget: CallBudget): Promise<SearchResult[]> {
    const response = await page.goto('https://www.bing.com', {
      waitUntil: 'domcontentloaded', timeout: budget.timeout(OPERATION_TIMEOUTS.searchRequest),
    });
    if (response?.status() >= 400) throw new Error(`Bing returned HTTP ${response.status()}`);
    await page.waitForSelector('#sb_form_q', { timeout: budget.timeout(OPERATION_TIMEOUTS.formSelector) });
    await page.fill('#sb_form_q', query, { timeout: budget.timeout(OPERATION_TIMEOUTS.formSelector) });
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: budget.timeout(OPERATION_TIMEOUTS.searchRequest) }),
      page.click('#search_icon', { timeout: budget.timeout(OPERATION_TIMEOUTS.formSelector) }),
    ]);
    await page.waitForSelector('.b_algo, .b_result', {
      timeout: budget.timeout(OPERATION_TIMEOUTS.searchSelector),
    }).catch(() => undefined);
    budget.remaining();
    return this.parseBingResults(await page.content(), numResults, page.url());
  }

  private async tryDirectBingSearch(page: any, query: string, numResults: number, budget: CallBudget): Promise<SearchResult[]> {
    const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(query)}&count=${Math.min(numResults, 10)}&cvid=${this.generateConversationId()}`;
    const response = await page.goto(searchUrl, {
      waitUntil: 'domcontentloaded', timeout: budget.timeout(OPERATION_TIMEOUTS.searchRequest),
    });
    if (response?.status() >= 400) throw new Error(`Bing returned HTTP ${response.status()}`);
    await page.waitForSelector('.b_algo, .b_result', {
      timeout: budget.timeout(OPERATION_TIMEOUTS.searchSelector),
    }).catch(() => undefined);
    budget.remaining();
    return this.parseBingResults(await page.content(), numResults, page.url());
  }

  private generateConversationId(): string {
    // Generate a conversation ID similar to Bing's format (32 hex characters)
    const chars = '0123456789ABCDEF';
    let cvid = '';
    for (let i = 0; i < 32; i++) {
      cvid += chars[Math.floor(Math.random() * chars.length)];
    }
    return cvid;
  }


  private async tryDuckDuckGoSearch(
    query: string, numResults: number, timeout: number, state: SearchEngineState | undefined, budget: CallBudget,
  ): Promise<SearchResult[]> {
    return this.browserPool.withHttp(async () => {
      budget.remaining();
      if (state) state.attempts = 1;
      const response = await axios.get('https://html.duckduckgo.com/html/', {
        params: { q: query }, signal: budget.signal,
        headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36' },
        timeout: budget.timeout(timeout), maxContentLength: 10 * 1024 * 1024,
        validateStatus: status => status < 400,
      });
      return this.parseDuckDuckGoResults(response.data, numResults, response.request?.res?.responseUrl ?? 'https://html.duckduckgo.com/html/');
    }, budget);
  }

  private parseBraveResults(html: string, maxResults: number, baseUrl = 'https://search.brave.com/'): SearchResult[] {
    console.log(`[SearchEngine] Parsing Brave HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    baseUrl = this.searchPageBase($, baseUrl);
    const results: SearchResult[] = [];

    // Brave result selectors
    const resultSelectors = [
      '[data-type="web"]',     // Main Brave results
      '.result',               // Alternative format
      '.fdb'                   // Brave specific format
    ];
    
    let foundResults = false;
    
    for (const selector of resultSelectors) {
      if (foundResults && results.length >= maxResults) break;
      
      console.log(`[SearchEngine] Trying Brave selector: ${selector}`);
      const elements = $(selector);
      console.log(`[SearchEngine] Found ${elements.length} elements with selector ${selector}`);
      
      elements.each((_index, element) => {
        if (results.length >= maxResults) return false;

        const $element = $(element);
        
        // Try multiple title selectors for Brave
        const titleSelectors = [
          '.title a',              // Brave specific
          'h2 a',                  // Common format  
          '.result-title a',       // Alternative format
          'a[href*="://"]',        // Any external link
          '.snippet-title a'       // Snippet title
        ];
        
        let title = '';
        let url = '';
        
        for (const titleSelector of titleSelectors) {
          const $titleElement = $element.find(titleSelector).first();
          if ($titleElement.length) {
            title = $titleElement.text().trim();
            url = $titleElement.attr('href') || '';
            console.log(`[SearchEngine] Brave found title with ${titleSelector}: "${title}"`);
            if (title && url && url.startsWith('http')) {
              break;
            }
          }
        }
        
        // Try multiple snippet selectors for Brave
        const snippetSelectors = [
          '.snippet-content',      // Brave specific
          '.snippet',              // Generic
          '.description',          // Alternative
          'p'                      // Fallback paragraph
        ];
        
        let snippet = '';
        for (const snippetSelector of snippetSelectors) {
          const $snippetElement = $element.find(snippetSelector).first();
          if ($snippetElement.length) {
            snippet = $snippetElement.text().trim();
            break;
          }
        }
        
        if (url && this.isValidSearchUrl(url)) {
          console.log(`[SearchEngine] Brave found: "${title}" -> "${url}"`);
          results.push({
            title,
            url: this.cleanBraveUrl(url, baseUrl),
            observedUrl: url,
            description: snippet,
          });
          foundResults = true;
        }
      });
    }

    console.log(`[SearchEngine] Brave found ${results.length} results`);
    return results;
  }

  private parseBingResults(html: string, maxResults: number, baseUrl = 'https://www.bing.com/'): SearchResult[] {
    console.error(`[SearchEngine] BING: Parsing HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    baseUrl = this.searchPageBase($, baseUrl);
    const results: SearchResult[] = [];


    // Bing result selectors
    const resultSelectors = [
      '.b_algo',     // Main Bing results
      '.b_result',   // Alternative Bing format
      '.b_card'      // Card format
    ];
    
    console.error(`[SearchEngine] BING: Checking for result elements...`);
    
    // Log counts for all selectors first
    for (const selector of resultSelectors) {
      const elements = $(selector);
      console.error(`[SearchEngine] BING: Found ${elements.length} elements with selector "${selector}"`);
    }
    
    let foundResults = false;
    
    for (const selector of resultSelectors) {
      if (foundResults && results.length >= maxResults) break;
      
      const elements = $(selector);
      if (elements.length === 0) continue;
      
      elements.each((_index, element) => {
        if (results.length >= maxResults) return false;

        const $element = $(element);
        
        // Try multiple title selectors for Bing
        const titleSelectors = [
          'h2 a',           // Standard Bing format
          '.b_title a',     // Alternative format
          'a[data-seid]'    // Bing specific
        ];
        
        let title = '';
        let url = '';
        
        for (const titleSelector of titleSelectors) {
          const $titleElement = $element.find(titleSelector).first();
          if ($titleElement.length) {
            title = $titleElement.text().trim();
            url = $titleElement.attr('href') || '';
            console.log(`[SearchEngine] Bing found title with ${titleSelector}: "${title}"`);
            break;
          }
        }
        
        // Try multiple snippet selectors for Bing
        const snippetSelectors = [
          '.b_caption p',           // Standard Bing snippet
          '.b_snippet',             // Alternative format
          '.b_descript',            // Description format
          '.b_caption',             // Caption without p tag
          '.b_caption > span',      // Caption span
          '.b_excerpt',             // Excerpt format
          'p',                      // Any paragraph in the result
          '.b_algo_content p',      // Content paragraph
          '.b_algo_content',        // Full content area
          '.b_context'              // Context information
        ];
        
        let snippet = '';
        for (const snippetSelector of snippetSelectors) {
          const $snippetElement = $element.find(snippetSelector).first();
          if ($snippetElement.length) {
            const candidateSnippet = $snippetElement.text().trim();
            if (candidateSnippet) {
              snippet = candidateSnippet;
              console.log(`[SearchEngine] Bing found snippet with ${snippetSelector}: "${snippet.substring(0, 100)}..."`);
              break;
            }
          }
        }
        
        if (url && this.isValidSearchUrl(url)) {
          console.log(`[SearchEngine] Bing found: "${title}" -> "${url}"`);
          results.push({
            title,
            url: this.cleanBingUrl(url, baseUrl),
            observedUrl: url,
            description: snippet,
          });
          foundResults = true;
        }
      });
    }

    console.log(`[SearchEngine] Bing found ${results.length} results`);
    return results;
  }

  private parseDuckDuckGoResults(html: string, maxResults: number, baseUrl = 'https://html.duckduckgo.com/html/'): SearchResult[] {
    console.log(`[SearchEngine] Parsing DuckDuckGo HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    baseUrl = this.searchPageBase($, baseUrl);
    const results: SearchResult[] = [];

    // DuckDuckGo results are in .result elements
    $('.result').each((_index, element) => {
      if (results.length >= maxResults) return false;

      const $element = $(element);
      
      // Extract title and URL
      const $titleElement = $element.find('.result__title a');
      const title = $titleElement.text().trim();
      const url = $titleElement.attr('href');
      
      // Extract snippet
      const snippet = $element.find('.result__snippet').text().trim();
      
      if (url && this.isValidSearchUrl(url)) {
        console.log(`[SearchEngine] DuckDuckGo found: "${title}" -> "${url}"`);
        results.push({
          title,
          url: this.cleanDuckDuckGoUrl(url, baseUrl),
          observedUrl: url,
          description: snippet,
        });
      }
    });

    console.log(`[SearchEngine] DuckDuckGo found ${results.length} results`);
    return results;
  }

  private searchPageBase($: cheerio.CheerioAPI, finalUrl: string): string {
    const href = $('base[href]').first().attr('href');
    try {
      const base = new URL(href ?? finalUrl, finalUrl);
      return ['http:', 'https:'].includes(base.protocol) ? base.href : finalUrl;
    } catch { return finalUrl; }
  }

  private isValidSearchUrl(url: string): boolean {
    try {
      return ['http:', 'https:'].includes(new URL(url, 'https://www.bing.com').protocol);
    } catch { return false; }
  }

  private cleanBraveUrl(url: string, baseUrl = 'https://search.brave.com/'): string {
    return new URL(url, baseUrl).href;
  }

  private cleanBingUrl(url: string, baseUrl = 'https://www.bing.com/'): string {
    return new URL(url, baseUrl).href;
  }

  private cleanDuckDuckGoUrl(url: string, baseUrl = 'https://html.duckduckgo.com/html/'): string {
    const parsed = new URL(url, baseUrl);
    const target = parsed.searchParams.get('uddg');
    if ((parsed.hostname === 'duckduckgo.com' || parsed.hostname.endsWith('.duckduckgo.com'))
      && parsed.pathname === '/l/' && target) {
      // URLSearchParams has already decoded this observed target once.
      return new URL(target, parsed).href;
    }
    return parsed.href;
  }
}
