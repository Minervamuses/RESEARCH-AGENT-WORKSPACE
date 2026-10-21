import axios from 'axios';
import * as cheerio from 'cheerio';
import { Page } from 'playwright';
import { ContentExtractionOptions, SearchResult } from './types.js';
import { cleanText, getWordCount, getContentPreview, generateTimestamp, isPdfUrl, resolveContentLimit, limitContent } from './utils.js';
import { BrowserPool } from './browser-pool.js';

export class EnhancedContentExtractor {
  private readonly defaultTimeout: number;
  private readonly maxContentLength: number;
  private browserPool: BrowserPool;
  private fallbackThreshold: number;

  constructor() {
    this.defaultTimeout = parseInt(process.env.DEFAULT_TIMEOUT || '6000', 10);
    
    this.maxContentLength = resolveContentLimit();

    this.browserPool = new BrowserPool();
    this.fallbackThreshold = parseInt(process.env.BROWSER_FALLBACK_THRESHOLD || '3', 10);
    
    console.log(`[EnhancedContentExtractor] Configuration: timeout=${this.defaultTimeout}, maxContentLength=${this.maxContentLength}, fallbackThreshold=${this.fallbackThreshold}`);
  }

  async extractContent(options: ContentExtractionOptions): Promise<string> {
    const { url } = options;
    const effectiveLimit = resolveContentLimit(options.maxContentLength);
    
    console.log(`[EnhancedContentExtractor] Starting extraction for: ${url}`);
    
    // First, try with regular HTTP client (faster)
    try {
      const content = await this.extractWithAxios(options);
      console.log(`[EnhancedContentExtractor] Successfully extracted with axios: ${content.length} chars`);
      return limitContent(content, effectiveLimit);
    } catch (error) {
      console.log(`[EnhancedContentExtractor] Axios failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      
      // Check if this looks like a case where browser would help
      if (this.shouldUseBrowser(error, url)) {
        console.log(`[EnhancedContentExtractor] Falling back to headless browser for: ${url}`);
        try {
          const content = await this.extractWithBrowser(options);
          console.log(`[EnhancedContentExtractor] Successfully extracted with browser: ${content.length} chars`);
          return limitContent(content, effectiveLimit);
        } catch (browserError) {
          console.error(`[EnhancedContentExtractor] Browser extraction also failed:`, browserError);
          throw new Error(`Both axios and browser extraction failed for ${url}`);
        }
      } else {
        throw error;
      }
    }
  }

  private async extractWithAxios(options: ContentExtractionOptions): Promise<string> {
    const { url, timeout = this.defaultTimeout, maxContentLength = this.maxContentLength } = options;
    
    const response = await axios.get(url, {
      headers: this.getRandomHeaders(),
      timeout,
      // Remove maxContentLength from axios config - handle truncation manually
      validateStatus: (status: number) => status < 400,
    });

    let content = this.parseContent(response.data, response.request?.res?.responseUrl ?? url);
    
    if (!content.trim()) throw Object.assign(new Error('No text extracted from HTTP response'), { reason: 'empty_text' });

    return content;
  }

  private async extractWithBrowser(options: ContentExtractionOptions): Promise<string> {
    const { url, timeout = this.defaultTimeout } = options;
    
    const browser = await this.browserPool.getBrowser();
    const browserType = this.browserPool.getLastUsedBrowserType();
    
    try {
      // Create context options based on browser capabilities
      const baseContextOptions = {
        userAgent: this.getRandomUserAgent(),
        viewport: this.getRandomViewport(),
        locale: 'en-US',
        timezoneId: this.getRandomTimezone(),
        // Simulate real device characteristics
        deviceScaleFactor: Math.random() > 0.5 ? 1 : 2,
        hasTouch: Math.random() > 0.7,
      };

      // Firefox doesn't support isMobile option - check multiple ways to ensure detection
      const isFirefox = browserType === 'firefox' || 
                       browserType.includes('firefox') || 
                       browser.constructor.name.toLowerCase().includes('firefox');
      
      const contextOptions = isFirefox
        ? baseContextOptions 
        : { ...baseContextOptions, isMobile: Math.random() > 0.8 };

      // Create a new context for each request (isolation)
      const context = await browser.newContext(contextOptions);

      // Add stealth scripts to avoid detection
      await context.addInitScript(() => {
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined,
        });

        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
          get: () => [1, 2, 3, 4, 5],
        });

        // Mock languages
        Object.defineProperty(navigator, 'languages', {
          get: () => ['en-US', 'en'],
        });

        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
          parameters.name === 'notifications' ?
            Promise.resolve({ state: 'default' } as unknown as PermissionStatus) :
            originalQuery(parameters)
        );

        // Remove automation indicators
        const windowWithChrome = window as any;
        if (windowWithChrome.chrome) {
          delete windowWithChrome.chrome.app;
          delete windowWithChrome.chrome.runtime;
        }
      });

      const page = await context.newPage();
      
      // Set up request interception to block unnecessary resources
      await page.route('**/*', (route) => {
        const resourceType = route.request().resourceType();
        
        // Block images, fonts, and other non-essential resources for faster loading
        if (['image', 'font', 'media'].includes(resourceType)) {
          route.abort();
        } else {
          route.continue();
        }
      });

      // Navigate with realistic options and better error handling
      console.log(`[BrowserExtractor] Navigating to ${url}`);
      
      try {
        await page.goto(url, { 
          waitUntil: 'domcontentloaded', // Don't wait for all resources
          timeout: Math.min(timeout, 8000) // Reduced timeout, max 8 seconds
        });
      } catch (gotoError) {
        // Handle specific protocol errors
        const errorMessage = gotoError instanceof Error ? gotoError.message : String(gotoError);
        
        if (errorMessage.includes('ERR_HTTP2_PROTOCOL_ERROR') || errorMessage.includes('HTTP2')) {
          console.log(`[BrowserExtractor] HTTP/2 error detected, trying with HTTP/1.1`);
          
          // Create a new context with HTTP/1.1 preference
          await context.close();
          const http1Context = await browser.newContext({
            userAgent: this.getRandomUserAgent(),
            viewport: this.getRandomViewport(),
            locale: 'en-US',
            timezoneId: this.getRandomTimezone(),
            extraHTTPHeaders: {
              'Connection': 'keep-alive',
              'Upgrade-Insecure-Requests': '1'
            }
          });
          
          const http1Page = await http1Context.newPage();
          
          // Disable HTTP/2 by intercepting requests
          await http1Page.route('**/*', (route) => {
            const resourceType = route.request().resourceType();
            if (['image', 'font', 'media'].includes(resourceType)) {
              route.abort();
            } else {
              route.continue();
            }
          });
          
          await http1Page.goto(url, { 
            waitUntil: 'domcontentloaded',
            timeout: Math.min(timeout, 6000)
          });
          
          // Quick content extraction
          const html = await http1Page.content();
          const content = this.parseContent(html, http1Page.url());
          await http1Context.close();
          return content;
        } else {
          throw gotoError;
        }
      }

      // Quick human simulation - reduced time
      await page.mouse.move(Math.random() * 100, Math.random() * 100);
      
      // Reduced wait time for dynamic content
      await page.waitForTimeout(500 + Math.random() * 1000);

      // Quick check for main content without long wait
      try {
        await page.waitForSelector('article, main, .content, .post-content, .entry-content', {
          timeout: 2000
        });
      } catch {
        console.log(`[BrowserExtractor] No main content selector found, proceeding anyway`);
      }

      // Extract content using the same logic as axios version
      const html = await page.content();
      const content = this.parseContent(html, page.url());

      await context.close();
      return content;

    } catch (error) {
      console.error(`[BrowserExtractor] Browser extraction failed for ${url}:`, error);
      throw error;
    }
  }

  private async simulateHumanBehavior(page: Page): Promise<void> {
    try {
      // Random mouse movements
      await page.mouse.move(
        Math.random() * 800,
        Math.random() * 600
      );

      // Random scroll (common human behavior)
      const scrollY = Math.random() * 500;
      await page.evaluate((y) => window.scrollTo(0, y), scrollY);

      // Small random delay
      await page.waitForTimeout(500 + Math.random() * 1000);

      // Sometimes click somewhere innocuous
      if (Math.random() > 0.7) {
        try {
          await page.click('body', { timeout: 1000 });
        } catch {
          // Ignore click failures
        }
      }
    } catch {
      // Ignore simulation errors
      console.log(`[BrowserExtractor] Behavior simulation failed, continuing`);
    }
  }

  private shouldUseBrowser(error: any, _url: string): boolean {
    return error.reason === 'empty_text'
      || [403, 429, 503].includes(error.response?.status)
      || ['ECONNABORTED', 'ETIMEDOUT', 'ECONNRESET'].includes(error.code);
  }

  private getRandomHeaders(): Record<string, string> {
    const browsers = [
      {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'sec-ch-ua-platform': '"Windows"',
      },
      {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'sec-ch-ua-platform': '"macOS"',
      },
      {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'sec-ch-ua-platform': '"Linux"',
      }
    ];

    const browser = browsers[Math.floor(Math.random() * browsers.length)];
    
    return {
      ...browser,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'DNT': '1',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
      'Sec-Fetch-User': '?1',
      'Cache-Control': 'max-age=0',
      'sec-ch-ua-mobile': '?0',
    };
  }

  private getRandomUserAgent(): string {
    const userAgents = [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
    ];
    
    return userAgents[Math.floor(Math.random() * userAgents.length)];
  }

  private getRandomViewport(): { width: number; height: number } {
    const viewports = [
      { width: 1920, height: 1080 },
      { width: 1366, height: 768 },
      { width: 1440, height: 900 },
      { width: 1536, height: 864 },
      { width: 1280, height: 720 },
    ];
    
    return viewports[Math.floor(Math.random() * viewports.length)];
  }

  private getRandomTimezone(): string {
    const timezones = [
      'America/New_York',
      'America/Los_Angeles',
      'America/Chicago',
      'Europe/London',
      'Europe/Berlin',
      'Asia/Tokyo',
    ];
    
    return timezones[Math.floor(Math.random() * timezones.length)];
  }

  async extractContentForResults(results: SearchResult[], targetCount: number = results.length, maxContentLength?: number): Promise<SearchResult[]> {
    console.log(`[EnhancedContentExtractor] Processing up to ${results.length} results to get ${targetCount} non-PDF results`);
    
    // Filter out PDF files first
    const nonPdfResults = results.filter(result => !isPdfUrl(result.url));
    const resultsToProcess = nonPdfResults.slice(0, Math.min(targetCount * 2, 10)); // Process extra to account for failures
    
    console.log(`[EnhancedContentExtractor] Processing ${resultsToProcess.length} non-PDF results concurrently`);
    
    // Process results concurrently with timeout
    const extractionPromises = resultsToProcess.map(async (result): Promise<SearchResult> => {
      try {
        // Use a race condition with timeout to prevent hanging
        const extractionPromise = this.extractContent({ 
          url: result.url, 
          timeout: 6000,
          maxContentLength
        });
        
        const timeoutPromise = new Promise<never>((_, reject) => {
          setTimeout(() => reject(new Error('Content extraction timeout')), 8000);
        });
        
        const content = await Promise.race([extractionPromise, timeoutPromise]);
        const cleanedContent = content;
        
        console.log(`[EnhancedContentExtractor] Successfully extracted: ${result.url}`);
        return {
          ...result,
          fullContent: cleanedContent,
          contentPreview: getContentPreview(cleanedContent),
          wordCount: getWordCount(cleanedContent),
          timestamp: generateTimestamp(),
          fetchStatus: 'success' as const,
        };
      } catch (error) {
        console.log(`[EnhancedContentExtractor] Failed to extract: ${result.url} - ${error instanceof Error ? error.message : 'Unknown error'}`);
        return {
          ...result,
          fullContent: '',
          contentPreview: '',
          wordCount: 0,
          timestamp: generateTimestamp(),
          fetchStatus: 'error' as const,
          error: this.getSpecificErrorMessage(error),
        };
      }
    });
    
    // Wait for all extractions to complete
    const allResults = await Promise.all(extractionPromises);
    
    // Return successful results first, up to targetCount
    const successfulResults = allResults.filter(r => r.fetchStatus === 'success');
    const failedResults = allResults.filter(r => r.fetchStatus === 'error');
    
    // Combine successful and failed results, prioritizing successful ones
    const enhancedResults = [
      ...successfulResults.slice(0, targetCount),
      ...failedResults.slice(0, Math.max(0, targetCount - successfulResults.length))
    ].slice(0, targetCount);
    
    console.log(`[EnhancedContentExtractor] Completed processing ${resultsToProcess.length} results, extracted ${successfulResults.length} successful/${failedResults.length} failed`);
    return enhancedResults;
  }

  private parseContent(html: string, finalUrl?: string): string {
    const $ = cheerio.load(html);
    $('script, style, noscript, template').remove();
    let baseUrl = finalUrl;
    const declaredBase = $('base[href]').first().attr('href');
    if (declaredBase) {
      try {
        const resolved = new URL(declaredBase, finalUrl);
        if (['http:', 'https:'].includes(resolved.protocol)) baseUrl = resolved.href;
      } catch { /* Retain the actual final URL when the declared base is invalid. */ }
    }
    const children = (node: any): string => (node.children ?? []).map(render).join('');
    const render = (node: any): string => {
      if (node.type === 'text') return (node.data ?? '').replace(/\s+/g, ' ');
      if (!node.tagName) return children(node);
      const tag = node.tagName.toLowerCase();
      const element = $(node);
      if (tag === 'pre') {
        const text = element.text().replace(/\r\n?/g, '\n');
        const runs = text.match(/`+/g) ?? [];
        const fence = '`'.repeat(Math.max(3, ...runs.map(run => run.length + 1)));
        return `\n\n${fence}\n${text}\n${fence}\n\n`;
      }
      if (tag === 'code') {
        const text = element.text();
        const fence = '`'.repeat(Math.max(1, ...(text.match(/`+/g) ?? []).map(run => run.length + 1)));
        return `${fence}${text}${fence}`;
      }
      if (tag === 'img') {
        const alt = element.attr('alt');
        return alt ? `[Image alt text: ${alt}]` : '';
      }
      if (tag === 'table') {
        const rows = element.find('tr').map((_i, row) =>
          $(row).children('th, td').map((_j, cell) => children(cell).trim()).get().join(' | '),
        ).get();
        return `\n\n[Table rows; span structure simplified]\n${rows.join('\n')}\n\n`;
      }
      const text = children(node);
      if (tag === 'a') {
        const href = element.attr('href');
        if (!href) return text;
        try {
          const url = new URL(href, baseUrl);
          if (['http:', 'https:'].includes(url.protocol)) {
            return `[${text.trim() || href}](<${url.href}>)`;
          }
        } catch { /* Unsupported or invalid addresses are source text, not navigation. */ }
        return `${text} [non-navigable href: ${href}]`;
      }
      if (/^h[1-6]$/.test(tag)) return `\n\n${'#'.repeat(Number(tag[1]))} ${text.trim()}\n\n`;
      if (tag === 'br') return '\n';
      if (tag === 'li') return `\n- ${text.trim()}\n`;
      if (tag === 'figcaption') return `\nCaption: ${text.trim()}\n`;
      if (['p', 'div', 'section', 'article', 'main', 'blockquote', 'ul', 'ol', 'figure', 'tr'].includes(tag)) {
        return `\n\n${text.trim()}\n\n`;
      }
      return text;
    };
    const main = $('main, article, [role="main"]').first();
    const root = main.length ? main : $('body');
    return children(root[0]).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  private getSpecificErrorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        return 'Request timeout';
      }
      if (error.response?.status === 403) {
        return '403 Forbidden - Access denied';
      }
      if (error.response?.status === 404) {
        return '404 Not found';
      }
      if (error.message.includes('maxContentLength')) {
        return 'Content too long';
      }
      if (error.response?.status) {
        return `HTTP ${error.response.status}: ${error.message}`;
      }
      return `Network error: ${error.message}`;
    }
    
    return error instanceof Error ? error.message : 'Unknown error';
  }

  async closeAll(): Promise<void> {
    await this.browserPool.closeAll();
  }
}