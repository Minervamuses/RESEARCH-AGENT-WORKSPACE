import axios from 'axios';
import * as cheerio from 'cheerio';
import { SearchOptions, SearchResult, SearchResultWithMetadata, SearchEngineState } from './types.js';
import { generateTimestamp, sanitizeQuery } from './utils.js';
import { RateLimiter } from './rate-limiter.js';
import { BrowserPool, sharedBrowserPool } from './browser-pool.js';

export class SearchEngine {
  private readonly rateLimiter: RateLimiter;
  private browserPool: BrowserPool;

  constructor(pool: BrowserPool = sharedBrowserPool) {
    this.rateLimiter = new RateLimiter(10); // 10 requests per minute
    this.browserPool = pool;
  }

  async search(options: SearchOptions): Promise<SearchResultWithMetadata> {
    const { query, numResults = 5, timeout = 10000 } = options;
    const sanitizedQuery = sanitizeQuery(query);
    return this.rateLimiter.execute(async () => {
      const approaches = [
        { method: this.tryBrowserBingSearch.bind(this), name: 'Browser Bing' },
        { method: this.tryDuckDuckGoSearch.bind(this), name: 'Axios DuckDuckGo' },
        { method: this.tryBrowserBraveSearch.bind(this), name: 'Browser Brave' },
      ];
      const results: SearchResult[] = [];
      const byUrl = new Map<string, SearchResult>();
      const engines: SearchEngineState[] = [];
      for (const approach of approaches) {
        const state: SearchEngineState = {
          name: approach.name, attempted: false, attempts: 0,
          parsedCount: 0, status: 'strategy_stopped',
        };
        engines.push(state);
        if (results.length >= numResults) continue;
        state.attempted = true;
        try {
          const batch = await approach.method(sanitizedQuery, numResults, Math.min(timeout, 4000), state);
          state.parsedCount = batch.length;
          state.status = batch.length ? 'completed' : 'zero_parsed';
          for (const item of batch) {
            let url: URL;
            try {
              url = new URL(item.url);
              if (!['http:', 'https:'].includes(url.protocol)) continue;
            } catch { continue; }
            const key = url.href;
            const previous = byUrl.get(key);
            if (previous) {
              if (!previous.sourceEngines!.includes(approach.name)) previous.sourceEngines!.push(approach.name);
              continue;
            }
            if (results.length >= numResults) continue;
            const candidate: SearchResult = {
              ...item, url: key, observedUrl: item.observedUrl ?? item.url,
              sourceEngines: [approach.name], fetchStatus: 'not_requested',
              fullContent: '', contentPreview: '', wordCount: 0,
            };
            results.push(candidate);
            byUrl.set(key, candidate);
          }
        } catch (error) {
          state.status = 'error';
          state.error = error instanceof Error ? error.message : String(error);
        } finally {
          state.attempts = Math.max(1, state.attempts);
        }
      }
      const sources = [...new Set(results.flatMap(item => item.sourceEngines ?? []))];
      return { results, engines, engine: sources.join(', ') || 'None' };
    });
  }

  private async tryBrowserBraveSearch(query: string, numResults: number, timeout: number, state?: SearchEngineState): Promise<SearchResult[]> {
    for (let attempt = 1; attempt <= 2; attempt++) {
      if (state) state.attempts = attempt;
      try {
        return await this.browserPool.withPage(async page => {
          const response = await page.goto(`https://search.brave.com/search?q=${encodeURIComponent(query)}&source=web`, {
            waitUntil: 'domcontentloaded', timeout,
          });
          const status = response?.status();
          if (status !== undefined && status >= 400) {
            throw Object.assign(new Error(`Brave returned HTTP ${status}`), { braveBlocked: true });
          }
          await page.waitForSelector('[data-type="web"]', { timeout: 3000 }).catch(() => undefined);
          return this.parseBraveResults(await page.content(), numResults);
        });
      } catch (error) {
        if (attempt === 2 || (error as { braveBlocked?: boolean })?.braveBlocked) throw error;
      }
    }
    return [];
  }

  private async tryBrowserBingSearch(query: string, numResults: number, timeout: number, state?: SearchEngineState): Promise<SearchResult[]> {
    return this.browserPool.withPage(async page => {
      if (state) state.attempts = 1;
      try {
        return await this.tryEnhancedBingSearch(page, query, numResults, timeout);
      } catch {
        if (state) state.attempts = 2;
        return this.tryDirectBingSearch(page, query, numResults, timeout);
      }
    });
  }

  private async tryEnhancedBingSearch(page: any, query: string, numResults: number, timeout: number, state?: SearchEngineState): Promise<SearchResult[]> {
    const debugBing = process.env.DEBUG_BING_SEARCH === 'true';
    console.error(`[SearchEngine] BING: Enhanced search - navigating to Bing homepage...`);
    
    // Navigate to Bing homepage first to establish proper session
    const startTime = Date.now();
    await page.goto('https://www.bing.com', { 
      waitUntil: 'domcontentloaded',
      timeout: timeout / 2
    });
    
    const loadTime = Date.now() - startTime;
    const pageTitle = await page.title();
    const currentUrl = page.url();
    console.error(`[SearchEngine] BING: Homepage loaded in ${loadTime}ms, title: "${pageTitle}", URL: ${currentUrl}`);
    
    // Wait a moment for page to fully load
    await page.waitForTimeout(500);
    
    // Find and use the search box (more realistic than direct URL)
    try {
      console.error(`[SearchEngine] BING: Looking for search form elements...`);
      await page.waitForSelector('#sb_form_q', { timeout: 2000 });
      console.error(`[SearchEngine] BING: Search box found, filling with query: "${query}"`);
      await page.fill('#sb_form_q', query);
      
      console.error(`[SearchEngine] BING: Clicking search button and waiting for navigation...`);
      // Submit the search form
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: timeout }),
        page.click('#search_icon')
      ]);
      
      const searchLoadTime = Date.now() - startTime;
      const searchPageTitle = await page.title();
      const searchPageUrl = page.url();
      console.error(`[SearchEngine] BING: Search completed in ${searchLoadTime}ms total, title: "${searchPageTitle}", URL: ${searchPageUrl}`);
      
    } catch (formError) {
      const errorMessage = formError instanceof Error ? formError.message : 'Unknown error';
      console.error(`[SearchEngine] BING: Search form submission failed: ${errorMessage}`);
      
      if (debugBing) {
        console.error(`[SearchEngine] BING: Form error details:`, formError);
      }
      
      throw formError;
    }
    
    // Wait for search results to load
    try {
      console.error(`[SearchEngine] BING: Waiting for search results to appear...`);
      await page.waitForSelector('.b_algo, .b_result', { timeout: 3000 });
      console.error(`[SearchEngine] BING: Search results selector found`);
    } catch {
      console.error(`[SearchEngine] BING: Search results selector not found, proceeding with page content anyway`);
    }

    const html = await page.content();
    console.error(`[SearchEngine] BING: Got page HTML with length: ${html.length} characters`);
    
    if (debugBing && html.length < 10000) {
      console.error(`[SearchEngine] BING: WARNING - HTML seems short, possible bot detection or error page`);
    }
    
    const results = this.parseBingResults(html, numResults);
    console.error(`[SearchEngine] BING: Enhanced search parsed ${results.length} results`);
    
    if (results.length === 0) {
      console.error(`[SearchEngine] BING: WARNING - No results found, possible parsing failure or empty search`);
      
      if (debugBing) {
        const sampleHtml = html.substring(0, 1000);
        console.error(`[SearchEngine] BING: Sample HTML for debugging:`, sampleHtml);
      }
    }
    
    return results;
  }

  private async tryDirectBingSearch(page: any, query: string, numResults: number, timeout: number): Promise<SearchResult[]> {
    const debugBing = process.env.DEBUG_BING_SEARCH === 'true';
    console.error(`[SearchEngine] BING: Direct search with enhanced parameters...`);
    
    // Generate a conversation ID (cvid) similar to what Bing uses
    const cvid = this.generateConversationId();
    
    // Construct URL with enhanced parameters based on successful manual searches
    const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(query)}&count=${Math.min(numResults, 10)}&form=QBLH&sp=-1&qs=n&cvid=${cvid}`;
    console.error(`[SearchEngine] BING: Navigating to direct URL: ${searchUrl}`);
    
    const startTime = Date.now();
    await page.goto(searchUrl, { 
      waitUntil: 'domcontentloaded',
      timeout: timeout
    });
    
    const loadTime = Date.now() - startTime;
    const pageTitle = await page.title();
    const currentUrl = page.url();
    console.error(`[SearchEngine] BING: Direct page loaded in ${loadTime}ms, title: "${pageTitle}", URL: ${currentUrl}`);

    // Wait for search results to load
    try {
      console.error(`[SearchEngine] BING: Waiting for search results to appear...`);
      await page.waitForSelector('.b_algo, .b_result', { timeout: 3000 });
      console.error(`[SearchEngine] BING: Search results selector found`);
    } catch {
      console.error(`[SearchEngine] BING: Search results selector not found, proceeding with page content anyway`);
    }

    const html = await page.content();
    console.error(`[SearchEngine] BING: Got page HTML with length: ${html.length} characters`);
    
    if (debugBing && html.length < 10000) {
      console.error(`[SearchEngine] BING: WARNING - HTML seems short, possible bot detection or error page`);
    }
    
    const results = this.parseBingResults(html, numResults);
    console.error(`[SearchEngine] BING: Direct search parsed ${results.length} results`);
    
    if (results.length === 0) {
      console.error(`[SearchEngine] BING: WARNING - No results found, possible parsing failure or empty search`);
      
      if (debugBing) {
        const sampleHtml = html.substring(0, 1000);
        console.error(`[SearchEngine] BING: Sample HTML for debugging:`, sampleHtml);
      }
    }
    
    return results;
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


  private async tryDuckDuckGoSearch(query: string, numResults: number, timeout: number, state?: SearchEngineState): Promise<SearchResult[]> {
    console.log(`[SearchEngine] Trying DuckDuckGo as fallback...`);
    
    try {
      const response = await this.browserPool.withHttp(() => axios.get('https://html.duckduckgo.com/html/', {
        params: {
          q: query,
        },
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
          'Accept-Encoding': 'gzip, deflate',
          'DNT': '1',
          'Connection': 'keep-alive',
          'Upgrade-Insecure-Requests': '1',
        },
        timeout,
        validateStatus: (status: number) => status < 400,
      }));

      console.log(`[SearchEngine] DuckDuckGo got response with status: ${response.status}`);
      
      const results = this.parseDuckDuckGoResults(response.data, numResults);
      console.log(`[SearchEngine] DuckDuckGo parsed ${results.length} results`);
      
      return results;
    } catch (error) {
      throw error;
    }
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
