import axios from 'axios';
import * as cheerio from 'cheerio';
import { SearchOptions, SearchResult, SearchResultWithMetadata, SearchEngineState } from './types.js';
import { generateTimestamp, sanitizeQuery } from './utils.js';
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
              sourceEngines: [approach.name], fetchStatus: 'not_requested',
              fullContent: '', contentPreview: '', wordCount: 0,
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
    const sources = [...new Set(results.flatMap(item => item.sourceEngines ?? []))];
    return { results, engines, engine: sources.join(', ') || 'None' };
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
          return this.parseBraveResults(await page.content(), numResults);
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
    return this.parseBingResults(await page.content(), numResults);
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
    return this.parseBingResults(await page.content(), numResults);
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
      return this.parseDuckDuckGoResults(response.data, numResults);
    }, budget);
  }

  private parseSearchResults(html: string, maxResults: number): SearchResult[] {
    console.log(`[SearchEngine] Parsing HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    const results: SearchResult[] = [];
    const timestamp = generateTimestamp();

    // Log what selectors we find - more comprehensive debugging
    const gElements = $('div.g');
    const sokobanElements = $('div[data-sokoban-container]');
    const tF2CxcElements = $('.tF2Cxc');
    const rcElements = $('.rc');
    const vedElements = $('[data-ved]');
    const h3Elements = $('h3');
    const linkElements = $('a[href]');
    
    console.log(`[SearchEngine] Found elements:`);
    console.log(`  - div.g: ${gElements.length}`);
    console.log(`  - div[data-sokoban-container]: ${sokobanElements.length}`);
    console.log(`  - .tF2Cxc: ${tF2CxcElements.length}`);
    console.log(`  - .rc: ${rcElements.length}`);
    console.log(`  - [data-ved]: ${vedElements.length}`);
    console.log(`  - h3: ${h3Elements.length}`);
    console.log(`  - a[href]: ${linkElements.length}`);
    
    // Try multiple approaches to find search results
    const searchResultSelectors = [
      'div.g',
      'div[data-sokoban-container]',
      '.tF2Cxc',
      '.rc',
      '[data-ved]',
      'div[jscontroller]'
    ];
    
    let foundResults = false;
    
    for (const selector of searchResultSelectors) {
      if (foundResults) break;
      
      console.log(`[SearchEngine] Trying selector: ${selector}`);
      const elements = $(selector);
      console.log(`[SearchEngine] Found ${elements.length} elements with selector ${selector}`);
      
      elements.each((_index, element) => {
        if (results.length >= maxResults) return false;
        
        const $element = $(element);
        
        // Try multiple title selectors
        const titleSelectors = ['h3', '.LC20lb', '.DKV0Md', 'a[data-ved]', '.r', '.s'];
        let title = '';
        let url = '';
        
        for (const titleSelector of titleSelectors) {
          const $title = $element.find(titleSelector).first();
          if ($title.length) {
            title = $title.text().trim();
            console.log(`[SearchEngine] Found title with ${titleSelector}: "${title}"`);
            
            // Try to find the link
            const $link = $title.closest('a');
            if ($link.length) {
              url = $link.attr('href') || '';
              console.log(`[SearchEngine] Found URL: "${url}"`);
            } else {
              // Try to find any link in the element
              const $anyLink = $element.find('a[href]').first();
              if ($anyLink.length) {
                url = $anyLink.attr('href') || '';
                console.log(`[SearchEngine] Found URL from any link: "${url}"`);
              }
            }
            break;
          }
        }
        
        // Try multiple snippet selectors
        const snippetSelectors = ['.VwiC3b', '.st', '.aCOpRe', '.IsZvec', '.s3v9rd', '.MUxGbd', '.aCOpRe', '.snippet-content'];
        let snippet = '';
        
        for (const snippetSelector of snippetSelectors) {
          const $snippet = $element.find(snippetSelector).first();
          if ($snippet.length) {
            snippet = $snippet.text().trim();
            console.log(`[SearchEngine] Found snippet with ${snippetSelector}: "${snippet.substring(0, 100)}..."`);
            break;
          }
        }
        
        if (title && url && this.isValidSearchUrl(url)) {
          console.log(`[SearchEngine] Adding result: ${title}`);
          results.push({
            title,
            url: this.cleanGoogleUrl(url),
            description: snippet,
            fullContent: '',
            contentPreview: '',
            wordCount: 0,
            timestamp,
            fetchStatus: 'not_requested',
          });
          foundResults = true;
        } else {
          console.log(`[SearchEngine] Skipping result: title="${title}", url="${url}", isValid=${this.isValidSearchUrl(url)}`);
        }
      });
    }

    console.log(`[SearchEngine] Found ${results.length} results with all selectors`);

    // If still no results, try a more aggressive approach - look for any h3 with links
    if (results.length === 0) {
      console.log(`[SearchEngine] No results found, trying aggressive h3 search...`);
      $('h3').each((_index, element) => {
        if (results.length >= maxResults) return false;
        
        const $h3 = $(element);
        const title = $h3.text().trim();
        const $link = $h3.closest('a');
        
        if ($link.length && title) {
          const url = $link.attr('href') || '';
          console.log(`[SearchEngine] Aggressive search found: "${title}" -> "${url}"`);
          
          if (this.isValidSearchUrl(url)) {
            results.push({
              title,
              url: this.cleanGoogleUrl(url),
              description: '',
              fullContent: '',
              contentPreview: '',
              wordCount: 0,
              timestamp,
              fetchStatus: 'not_requested',
            });
          }
        }
      });
      
      console.log(`[SearchEngine] Aggressive search found ${results.length} results`);
    }

    return results;
  }

  private parseBraveResults(html: string, maxResults: number): SearchResult[] {
    console.log(`[SearchEngine] Parsing Brave HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    const results: SearchResult[] = [];
    const timestamp = generateTimestamp();

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
        
        // If still no title, try getting it from any text content
        if (!title) {
          const textContent = $element.text().trim();
          const lines = textContent.split('\n').filter(line => line.trim().length > 0);
          if (lines.length > 0) {
            title = lines[0].trim();
            console.log(`[SearchEngine] Brave found title from text content: "${title}"`);
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
        
        if (title && url && this.isValidSearchUrl(url)) {
          console.log(`[SearchEngine] Brave found: "${title}" -> "${url}"`);
          results.push({
            title,
            url: this.cleanBraveUrl(url),
            observedUrl: url,
            description: snippet,
            fullContent: '',
            contentPreview: '',
            wordCount: 0,
            timestamp,
            fetchStatus: 'not_requested',
          });
          foundResults = true;
        }
      });
    }

    console.log(`[SearchEngine] Brave found ${results.length} results`);
    return results;
  }

  private parseBingResults(html: string, maxResults: number): SearchResult[] {
    const debugBing = process.env.DEBUG_BING_SEARCH === 'true';
    console.error(`[SearchEngine] BING: Parsing HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    const results: SearchResult[] = [];
    const timestamp = generateTimestamp();


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
            // Skip very short snippets or those that look like metadata
            if (candidateSnippet.length > 20 && !candidateSnippet.match(/^\d+\s*(min|sec|hour|day|week|month|year)/i)) {
              snippet = candidateSnippet;
              console.log(`[SearchEngine] Bing found snippet with ${snippetSelector}: "${snippet.substring(0, 100)}..."`);
              break;
            }
          }
        }
        
        if (title && url && this.isValidSearchUrl(url)) {
          console.log(`[SearchEngine] Bing found: "${title}" -> "${url}"`);
          results.push({
            title,
            url: this.cleanBingUrl(url),
            observedUrl: url,
            description: snippet,
            fullContent: '',
            contentPreview: '',
            wordCount: 0,
            timestamp,
            fetchStatus: 'not_requested',
          });
          foundResults = true;
        }
      });
    }

    console.log(`[SearchEngine] Bing found ${results.length} results`);
    return results;
  }

  private parseDuckDuckGoResults(html: string, maxResults: number): SearchResult[] {
    console.log(`[SearchEngine] Parsing DuckDuckGo HTML with length: ${html.length}`);
    
    const $ = cheerio.load(html);
    const results: SearchResult[] = [];
    const timestamp = generateTimestamp();

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
      
      if (title && url && this.isValidSearchUrl(url)) {
        console.log(`[SearchEngine] DuckDuckGo found: "${title}" -> "${url}"`);
        results.push({
          title,
          url: this.cleanDuckDuckGoUrl(url),
          observedUrl: url,
          description: snippet,
          fullContent: '',
          contentPreview: '',
          wordCount: 0,
          timestamp,
          fetchStatus: 'not_requested',
        });
      }
    });

    console.log(`[SearchEngine] DuckDuckGo found ${results.length} results`);
    return results;
  }

  private isValidSearchUrl(url: string): boolean {
    try {
      return ['http:', 'https:'].includes(new URL(url, 'https://www.bing.com').protocol);
    } catch { return false; }
  }

  private cleanGoogleUrl(url: string): string {
    // Handle Google's redirect URLs
    if (url.startsWith('/url?')) {
      try {
        const urlParams = new URLSearchParams(url.substring(5));
        const actualUrl = urlParams.get('q') || urlParams.get('url');
        if (actualUrl) {
          return actualUrl;
        }
      } catch {
        console.warn('Failed to parse Google redirect URL:', url);
      }
    }

    // Handle protocol-relative URLs
    if (url.startsWith('//')) {
      return 'https:' + url;
    }

    return url;
  }

  private cleanBraveUrl(url: string): string {
    return new URL(url, 'https://search.brave.com').href;
  }

  private cleanBingUrl(url: string): string {
    return new URL(url, 'https://www.bing.com').href;
  }

  private cleanDuckDuckGoUrl(url: string): string {
    // DuckDuckGo URLs are redirect URLs that need to be decoded
    if (url.startsWith('//duckduckgo.com/l/')) {
      try {
        // Extract the uddg parameter which contains the actual URL
        const urlParams = new URLSearchParams(url.substring(url.indexOf('?') + 1));
        const actualUrl = urlParams.get('uddg');
        if (actualUrl) {
          // Decode the URL
          const decodedUrl = actualUrl;
          console.log(`[SearchEngine] Decoded DuckDuckGo URL: ${decodedUrl}`);
          return decodedUrl;
        }
      } catch {
        console.log(`[SearchEngine] Failed to decode DuckDuckGo URL: ${url}`);
      }
    }
    
    // If it's a protocol-relative URL, add https:
    if (url.startsWith('//')) {
      return 'https:' + url;
    }
    
    return url;
  }

  async closeAll(): Promise<void> {
    await this.browserPool.closeAll();
  }
}
