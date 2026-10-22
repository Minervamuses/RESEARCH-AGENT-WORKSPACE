import { chromium, Browser, BrowserContext, Page } from 'playwright';
import pLimit from 'p-limit';
import { readFileSync } from 'node:fs';
import { parseInteger } from './utils.js';

export const OPERATION_TIMEOUTS = {
  launch: 10000, searchRequest: 4000, searchSelector: 3000,
  formSelector: 2000, pageRequest: 6000, pageTotal: 8000, cleanup: 1000, renderSettle: 3000,
} as const;

export function configuredTimeout(): number {
  const raw = process.env.DEFAULT_TIMEOUT ?? '300000';
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) < 1 || Number(raw) > 300000) {
    throw new Error('Invalid DEFAULT_TIMEOUT: integer milliseconds 1–300000 required');
  }
  return Number(raw);
}

/** FU03: one fixed normal Chrome UA; only the major version comes from the launched browser. */
export function normalUserAgent(browserVersion: string): string {
  return `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${browserVersion.split('.')[0]}.0.0.0 Safari/537.36`;
}

export function cleanupReserve(total: number): number {
  return Math.min(15000, Math.max(1500, total * 0.05), total / 2);
}

/** One call's monotonic work deadline and cancellation; no session state. */
export class CallBudget {
  private controller = new AbortController();
  private deadline: number;
  private timer: ReturnType<typeof setTimeout>;
  private parentAbort?: () => void;
  readonly signal = this.controller.signal;

  constructor(durationMs = configuredTimeout() - cleanupReserve(configuredTimeout()), parent?: AbortSignal) {
    this.deadline = performance.now() + Math.max(0, durationMs);
    this.timer = setTimeout(() => this.abort(Object.assign(new Error('Call deadline exceeded'), { code: 'ETIMEDOUT' })), Math.max(0, durationMs));
    if (parent) {
      this.parentAbort = () => this.abort(parent.reason);
      if (parent.aborted) this.parentAbort();
      else parent.addEventListener('abort', this.parentAbort, { once: true });
    }
    this.parent = parent;
  }
  private parent?: AbortSignal;

  abort(reason?: unknown): void {
    this.controller.abort(reason ?? Object.assign(new Error('Call cancelled'), { code: 'ERR_CANCELED' }));
  }
  remaining(): number {
    if (this.signal.aborted) throw this.signal.reason;
    const remaining = this.deadline - performance.now();
    if (remaining <= 0) {
      this.abort(Object.assign(new Error('Call deadline exceeded'), { code: 'ETIMEDOUT' }));
      throw this.signal.reason;
    }
    return remaining;
  }
  timeout(cap: number): number { return Math.max(1, Math.floor(Math.min(cap, this.remaining()))); }
  async wait<T>(promise: Promise<T>): Promise<T> {
    // Always attach handlers, including when cancellation arrived before this call.
    let onAbort: () => void = () => undefined;
    const cancelled = new Promise<never>((_resolve, reject) => {
      onAbort = () => reject(this.signal.reason);
      if (this.signal.aborted) onAbort();
      else this.signal.addEventListener('abort', onAbort, { once: true });
    });
    try { return await Promise.race([promise, cancelled]); }
    finally { this.signal.removeEventListener('abort', onAbort); }
  }
  child(cap: number): CallBudget { return new CallBudget(Math.min(cap, this.remaining()), this.signal); }
  dispose(): void {
    clearTimeout(this.timer);
    if (this.parentAbort) this.parent?.removeEventListener('abort', this.parentAbort);
  }
}

async function boundedClose(close: () => Promise<void>): Promise<boolean> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      close(),
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error('Resource cleanup timeout')), OPERATION_TIMEOUTS.cleanup);
      }),
    ]);
    return true;
  } catch (error) {
    console.error('Resource cleanup:', error);
    return false;
  } finally { if (timer) clearTimeout(timer); }
}

export class BrowserPool {
  private browser?: Browser;
  private launching?: Promise<Browser>;
  private browserWaiters = 0;
  private contexts = new Set<BrowserContext>();
  private damaged = false;
  private closing?: Promise<void>;
  private owned = new Map<number, string>();
  private readonly ownerFlag = `--web-search-owner=${process.pid}`;
  private readonly pages = pLimit(parseInteger(process.env.MAX_CONCURRENT_PAGES ?? 2, 'MAX_CONCURRENT_PAGES', 1, Number.MAX_SAFE_INTEGER));
  private readonly http = pLimit(parseInteger(process.env.MAX_CONCURRENT_HTTP ?? 2, 'MAX_CONCURRENT_HTTP', 1, Number.MAX_SAFE_INTEGER));

  constructor() {
    const headless = process.env.BROWSER_HEADLESS;
    if (headless !== undefined && !['true', 'false'].includes(headless)) {
      throw new Error('Invalid BROWSER_HEADLESS: true or false required');
    }
  }

  async getBrowser(budget?: CallBudget): Promise<Browser> {
    budget?.remaining();
    if (this.damaged) throw new Error('Browser cleanup incomplete; no new contexts allowed');
    this.browserWaiters++;
    try {
      if (this.browser?.isConnected()) return this.browser;
      if (!this.launching) {
        this.launching = chromium.launch({
          // FU02: Playwright's full Chromium in new headless mode, not the headless shell.
          channel: 'chromium',
          headless: process.env.BROWSER_HEADLESS !== 'false',
          timeout: budget?.timeout(OPERATION_TIMEOUTS.launch) ?? OPERATION_TIMEOUTS.launch,
          args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled', this.ownerFlag],
        }).then(async browser => {
          this.browser = browser;
          this.rememberBrowserProcesses();
          if (!this.closing && !this.browserWaiters && !this.contexts.size) await this.closeAll();
          return browser;
        }).finally(() => { this.launching = undefined; });
      }
      return budget ? await budget.wait(this.launching) : await this.launching;
    } finally { this.browserWaiters--; }
  }

  async withPage<T>(
    fn: (page: Page, context: BrowserContext) => Promise<T>, supplied?: CallBudget,
  ): Promise<T> {
    const budget = supplied ?? new CallBudget();
    try {
      return await budget.wait(this.pages(async () => {
        budget.remaining();
        const browser = await this.getBrowser(budget);
        const pendingContext = browser.newContext({ userAgent: normalUserAgent(browser.version()) }).then(async context => {
          this.contexts.add(context);
          if (budget.signal.aborted) {
            if (await boundedClose(() => context.close())) this.contexts.delete(context);
            else this.damaged = true;
            throw budget.signal.reason;
          }
          return context;
        });
        const context = await budget.wait(pendingContext);
        let closing: Promise<boolean> | undefined;
        const close = () => closing ??= boundedClose(() => context.close()).then(ok => {
          if (ok) this.contexts.delete(context);
          else this.damaged = true;
          return ok;
        });
        const onAbort = () => { void close(); };
        budget.signal.addEventListener('abort', onAbort, { once: true });
        try {
          budget.remaining();
          const page = await budget.wait(context.newPage());
          budget.remaining();
          return await budget.wait(fn(page, context));
        } finally {
          budget.signal.removeEventListener('abort', onAbort);
          await close();
        }
      }));
    } finally { if (!supplied) budget.dispose(); }
  }

  async withHttp<T>(fn: () => Promise<T>, supplied?: CallBudget): Promise<T> {
    const budget = supplied ?? new CallBudget();
    try {
      return await budget.wait(this.http(async () => {
        budget.remaining();
        return fn();
      }));
    } finally { if (!supplied) budget.dispose(); }
  }

  private rememberBrowserProcesses(): void {
    try {
      const children = readFileSync(`/proc/self/task/${process.pid}/children`, 'utf8').trim().split(/\s+/);
      for (const raw of children) {
        const pid = Number(raw);
        if (!pid) continue;
        const args = readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
        if (!args.includes(this.ownerFlag)) continue;
        const fields = readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' ');
        // Playwright launches Chromium in its own process group. Never kill a shared group.
        if (Number(fields[2]) === pid) this.owned.set(pid, fields[19]);
      }
    } catch (error) { console.error('Browser PID observation:', error); }
  }

  private killOwnedBrowsers(): void {
    for (const [pid, started] of this.owned) {
      try {
        const fields = readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' ');
        const args = readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
        if (fields[19] === started && Number(fields[2]) === pid && args.includes(this.ownerFlag)) {
          process.kill(-pid, 'SIGKILL');
        }
      } catch { /* Already exited. Identity mismatches are never terminated. */ }
    }
    this.owned.clear();
  }

  async closeAll(): Promise<void> {
    if (this.closing) return this.closing;
    this.closing = (async () => {
      this.rememberBrowserProcesses();
      let browser = this.browser;
      if (!browser && this.launching) {
        await boundedClose(async () => { browser = await this.launching; });
      }
      if (browser) await boundedClose(() => browser!.close());
      this.killOwnedBrowsers();
      this.browser = undefined;
      this.contexts.clear();
      this.damaged = false;
    })().finally(() => { this.closing = undefined; });
    return this.closing;
  }
}

export const sharedBrowserPool = new BrowserPool();
