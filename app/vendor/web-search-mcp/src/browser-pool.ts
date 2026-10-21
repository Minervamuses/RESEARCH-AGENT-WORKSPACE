import { chromium, Browser, BrowserContext, Page } from 'playwright';
import pLimit from 'p-limit';

export class BrowserPool {
  private browser?: Browser;
  private launching?: Promise<Browser>;
  private readonly pages = pLimit(2);
  private readonly http = pLimit(2);

  async getBrowser(): Promise<Browser> {
    if (this.browser?.isConnected()) return this.browser;
    if (!this.launching) {
      this.launching = chromium.launch({
        headless: process.env.BROWSER_HEADLESS !== 'false',
        args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
      }).then(browser => {
        this.browser = browser;
        return browser;
      }).finally(() => { this.launching = undefined; });
    }
    return this.launching;
  }

  async withPage<T>(fn: (page: Page, context: BrowserContext) => Promise<T>): Promise<T> {
    return this.pages(async () => {
      const browser = await this.getBrowser();
      const context = await browser.newContext();
      try {
        return await fn(await context.newPage(), context);
      } finally {
        await context.close().catch(error => console.error('Context cleanup:', error));
      }
    });
  }

  async withHttp<T>(fn: () => Promise<T>): Promise<T> {
    return this.http(fn);
  }

  async closeAll(): Promise<void> {
    const browser = this.browser ?? await this.launching?.catch(() => undefined);
    this.browser = undefined;
    if (browser) await browser.close().catch(error => console.error('Browser cleanup:', error));
  }
}

// The MCP server's search and content paths share this one process-owned pool.
export const sharedBrowserPool = new BrowserPool();
