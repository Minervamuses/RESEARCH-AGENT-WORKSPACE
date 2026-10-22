import axios from 'axios';
import * as cheerio from 'cheerio';
import type { Page } from 'playwright';
import { ContentExtractionOptions, SearchResult, PageRead } from './types.js';
import { resolveContentLimit, truncateMarkdown } from './utils.js';
import { BrowserPool, sharedBrowserPool, CallBudget, OPERATION_TIMEOUTS } from './browser-pool.js';

// Elements rendered as blocks by default; they only add separators and never remove text.
const BLOCK_TAGS = new Set([
  'address', 'article', 'aside', 'blockquote', 'dd', 'details', 'dialog', 'div', 'dl', 'dt',
  'fieldset', 'figure', 'footer', 'form', 'header', 'hgroup', 'hr', 'legend', 'main', 'menu',
  'nav', 'ol', 'optgroup', 'option', 'p', 'search', 'section', 'summary', 'tr', 'ul',
]);

const singleLine = (text: string): string => text.replace(/\s+/g, ' ').trim();

const pause = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

/** Settles to undefined when the promise fails or outlives a local cap. */
async function within<T>(promise: Promise<T>, ms: number): Promise<T | undefined> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise.catch(() => undefined),
      new Promise<undefined>(resolve => { timer = setTimeout(() => resolve(undefined), Math.max(0, ms)); }),
    ]);
  } finally { if (timer) clearTimeout(timer); }
}

/** The page's own title: head title first, never an inline SVG title, never the URL. */
function documentTitle($: cheerio.CheerioAPI): string | undefined {
  const head = $('head > title').first();
  const title = head.length ? head : $('title').filter((_i, node) => !$(node).parents('svg').length).first();
  return singleLine(title.text()) || undefined;
}

export class EnhancedContentExtractor {
  constructor(private browserPool: BrowserPool = sharedBrowserPool) {}

  async extractContent(options: ContentExtractionOptions & { budget?: CallBudget }): Promise<PageRead> {
    const budget = options.budget ?? new CallBudget();
    const state: PageRead = {
      requestedUrl: options.url, status: 'not_attempted', attempts: [], content: '',
      maxContentLength: resolveContentLimit(options.maxContentLength),
      returnedLength: 0, truncated: false,
    };
    const attempt = async (transport: 'http' | 'browser'): Promise<boolean> => {
      const event: PageRead['attempts'][number] = { transport };
      const started = () => { budget.remaining(); state.attempts.push(event); };
      delete state.httpStatus;
      delete state.contentType;
      delete state.finalUrl;
      delete state.pageTitle;
      try {
        const text = transport === 'http'
          ? await this.browserPool.withHttp(() => {
              started();
              return this.extractWithAxios({ ...options, budget }, state);
            }, budget)
          : await this.extractWithBrowser({ ...options, budget }, state, started, event);
        event.status = state.httpStatus;
        if (state.status === 'unsupported_media') return true;
        Object.assign(state, truncateMarkdown(text, state.maxContentLength));
        state.status = text.trim() ? 'text' : 'empty_text';
        return state.status === 'text';
      } catch (error) {
        const err = (budget.signal.aborted ? budget.signal.reason : error) as any;
        const response = err.response;
        if (response) {
          state.httpStatus = response.status;
          state.contentType = response.headers?.['content-type'];
          state.finalUrl = response.request?.res?.responseUrl;
        }
        event.status = state.httpStatus;
        event.error = error instanceof Error ? error.message : String(error);
        state.error = event.error;
        state.status = !state.attempts.length ? 'not_attempted'
          : budget.signal.aborted && err.code !== 'ETIMEDOUT' ? 'cancelled'
          : err.code === 'ERR_CANCELED' ? 'cancelled'
          : ['ECONNABORTED', 'ETIMEDOUT'].includes(err.code) || err.name === 'TimeoutError' ? 'timeout'
          : err.reason === 'conversion_error' ? 'conversion_error' : 'http_error';
        return false;
      }
    };
    try {
      const complete = await attempt('http');
      if (!complete && !budget.signal.aborted && !['cancelled', 'conversion_error'].includes(state.status)
        && (state.status === 'empty_text' || state.status === 'timeout'
          || [403, 429, 503].includes(state.httpStatus ?? 0))) {
        await attempt('browser');
      }
      if (state.status === 'text') delete state.error;
      return state;
    } finally { if (!options.budget) budget.dispose(); }
  }

  private async extractWithAxios(options: ContentExtractionOptions & { budget: CallBudget }, state: PageRead): Promise<string> {
    const response = await axios.get(options.url, {
      responseType: 'arraybuffer', signal: options.budget.signal,
      timeout: options.budget.timeout(Math.min(options.timeout ?? OPERATION_TIMEOUTS.pageRequest, OPERATION_TIMEOUTS.pageRequest)),
      headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36' },
      maxContentLength: 10 * 1024 * 1024,
      validateStatus: status => status < 400,
    });
    state.httpStatus = response.status;
    state.contentType = response.headers['content-type']?.toString();
    state.finalUrl = response.request?.res?.responseUrl ?? options.url;
    return this.convertResponse(Buffer.from(response.data), state);
  }

  private convertResponse(bytes: Buffer, state: PageRead): string {
    const media = state.contentType?.split(';')[0].trim().toLowerCase();
    if (bytes.subarray(0, 5).toString('ascii') === '%PDF-'
      || !['text/html', 'application/xhtml+xml', 'text/plain'].includes(media ?? '')) {
      state.status = 'unsupported_media';
      state.error = `Unsupported media: ${state.contentType ?? 'unknown'}`;
      return '';
    }
    const text = bytes.toString('utf8');
    if (media === 'text/plain') return text.replace(/\r\n?/g, '\n').trim();
    try {
      state.pageTitle = documentTitle(cheerio.load(text));
      return this.parseContent(text, state.finalUrl);
    } catch (error) {
      throw Object.assign(error instanceof Error ? error : new Error(String(error)), { reason: 'conversion_error' });
    }
  }

  private async extractWithBrowser(
    options: ContentExtractionOptions & { budget: CallBudget }, state: PageRead, started: () => void,
    event: PageRead['attempts'][number],
  ): Promise<string> {
    return this.browserPool.withPage(async page => {
      started();
      const response = await page.goto(options.url, {
        waitUntil: 'domcontentloaded', timeout: options.budget.timeout(OPERATION_TIMEOUTS.pageRequest),
      });
      state.finalUrl = page.url();
      state.httpStatus = response?.status();
      state.contentType = response?.headers()['content-type'];
      if (state.httpStatus !== undefined && state.httpStatus >= 400) {
        throw new Error(`HTTP ${state.httpStatus}`);
      }
      const media = state.contentType?.split(';')[0].trim().toLowerCase();
      if (!['text/html', 'application/xhtml+xml', 'text/plain'].includes(media ?? '')) {
        state.status = 'unsupported_media';
        state.error = `Unsupported media: ${state.contentType ?? 'unknown'}`;
        return '';
      }
      const settle = media === 'text/plain' ? undefined : await this.settleRendering(page, options.budget);
      state.pageTitle = singleLine(await page.title()) || undefined;
      const text = media === 'text/plain' ? await page.locator('body').innerText()
        : this.parseContent(await page.content(), state.finalUrl);
      if (settle && !text.trim()) {
        event.error = state.error = `No visible text after waiting ${settle.waitedMs} ms for client rendering (limit ${settle.limitMs} ms)`;
      }
      return text;
    }, options.budget);
  }

  /** FA04: wait until the network is idle and the body has visible text, at most min(renderSettle, remaining budget). */
  private async settleRendering(page: Page, budget: CallBudget): Promise<{ waitedMs: number; limitMs: number }> {
    const limitMs = budget.timeout(OPERATION_TIMEOUTS.renderSettle);
    const begin = performance.now();
    const left = () => limitMs - (performance.now() - begin);
    let idle = false;
    page.waitForLoadState('networkidle', { timeout: limitMs }).then(() => { idle = true; }, () => undefined);
    // Poll from Node: a page-side waitForFunction needs eval, which a page CSP may forbid.
    while (left() > 0) {
      const text = await budget.wait(within(page.evaluate(() => document.body?.innerText ?? ''), left()));
      if (idle && text?.trim()) break;
      await budget.wait(pause(Math.max(0, Math.min(100, left()))));
    }
    return { waitedMs: Math.round(performance.now() - begin), limitMs };
  }

  async extractContentForResults(
    results: SearchResult[], targetCount = results.length, maxContentLength?: number, supplied?: CallBudget,
  ): Promise<SearchResult[]> {
    const budget = supplied ?? new CallBudget();
    try {
      return await Promise.all(results.slice(0, targetCount).map(async result => {
        let child = budget;
        try { child = budget.child(OPERATION_TIMEOUTS.pageTotal); } catch { /* Keep cancelled candidates. */ }
        try {
          const read = await this.extractContent({ url: result.url, maxContentLength, budget: child });
          return { ...result, read };
        } finally { if (child !== budget) child.dispose(); }
      }));
    } finally { if (!supplied) budget.dispose(); }
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
        // Only this table's own rows; a nested table renders once, inside its cell's single line.
        const rows = element.children('thead, tbody, tfoot, tr').get()
          .flatMap((group: any) => group.tagName.toLowerCase() === 'tr' ? [group] : $(group).children('tr').get())
          .map((row: any) => $(row).children('th, td').get().map((cell: any) => singleLine(children(cell))).join(' | '));
        const caption = singleLine(element.children('caption').get().map(children).join(' '));
        return `\n\n${caption ? `Table caption: ${caption}\n` : ''}[Table rows; span structure simplified]\n${rows.join('\n')}\n\n`;
      }
      const text = children(node);
      if (tag === 'a') {
        const href = element.attr('href');
        if (!href) return text;
        try {
          const url = new URL(href, baseUrl);
          if (['http:', 'https:'].includes(url.protocol)) {
            return `[${singleLine(text) || href}](<${url.href}>)`;
          }
        } catch { /* Unsupported or invalid addresses are source text, not navigation. */ }
        return `${text} [non-navigable href: ${href}]`;
      }
      if (/^h[1-6]$/.test(tag)) return `\n\n${'#'.repeat(Number(tag[1]))} ${text.trim()}\n\n`;
      if (tag === 'br') return '\n';
      if (tag === 'li') return `\n- ${text.trim()}\n`;
      if (tag === 'figcaption') return `\nCaption: ${text.trim()}\n`;
      if (BLOCK_TAGS.has(tag)) return `\n\n${text.trim()}\n\n`;
      return text;
    };
    // The whole body in source order; no main-content guess decides which text has value.
    const root = $('body').first()[0] ?? $.root()[0];
    return children(root).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  }
}
