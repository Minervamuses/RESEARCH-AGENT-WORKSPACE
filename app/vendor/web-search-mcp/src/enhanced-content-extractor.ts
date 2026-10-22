import axios from 'axios';
import * as cheerio from 'cheerio';
import type { Page, Response } from 'playwright';
import { ContentExtractionOptions, SearchResult, PageRead, PageReadAttempt } from './types.js';
import { resolveContentLimit, sanitizeErrorMessage, truncateMarkdown } from './utils.js';
import { BrowserPool, sharedBrowserPool, CallBudget, OPERATION_TIMEOUTS, boundedRead } from './browser-pool.js';

// Elements rendered as blocks by default; they only add separators and never remove text.
const BLOCK_TAGS = new Set([
  'address', 'article', 'aside', 'blockquote', 'dd', 'details', 'dialog', 'div', 'dl', 'dt',
  'fieldset', 'figure', 'footer', 'form', 'header', 'hgroup', 'hr', 'legend', 'main', 'menu',
  'nav', 'ol', 'optgroup', 'option', 'p', 'search', 'section', 'summary', 'tr', 'ul',
]);

const singleLine = (text: string): string => text.replace(/\s+/g, ' ').trim();

const pause = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

/** Removes trailing spaces and tabs line by line in linear time (no backtracking regex). */
function trimLineEnds(text: string): string {
  return text.split('\n').map(line => {
    let end = line.length;
    while (end > 0 && (line[end - 1] === ' ' || line[end - 1] === '\t')) end--;
    return line.slice(0, end);
  }).join('\n');
}

const READ_LIMIT_BYTES = 10 * 1024 * 1024;
const SUPPORTED_MEDIA = ['text/html', 'application/xhtml+xml', 'text/plain'];
const mediaType = (contentType?: string) => contentType?.split(';')[0].trim().toLowerCase();

/** Rethrows a conversion or truncation failure as conversion_error, never as a transport error. */
function converting<T>(convert: () => T): T {
  try { return convert(); } catch (error) {
    throw Object.assign(error instanceof Error ? error : new Error(String(error)), { reason: 'conversion_error' });
  }
}

/** FA03, after the HTML encoding sniffing order: BOM, Content-Type charset, meta prescan (HTML), UTF-8. */
function decodeBody(bytes: Buffer, contentType: string | undefined, html: boolean): { text: string; encoding: NonNullable<PageRead['encoding']> } {
  const bom: [number[], string][] = [[[0xef, 0xbb, 0xbf], 'utf-8'], [[0xfe, 0xff], 'utf-16be'], [[0xff, 0xfe], 'utf-16le']];
  const marked = bom.find(([mark]) => mark.every((byte, index) => bytes[index] === byte));
  let label: string | undefined = marked?.[1];
  let source: NonNullable<PageRead['encoding']>['source'] = 'BOM';
  if (!label) {
    label = /charset\s*=\s*["']?([^\s;"']+)/i.exec(contentType ?? '')?.[1];
    source = 'Content-Type charset';
  }
  if (!label && html) {
    // Covers <meta charset> and <meta http-equiv="Content-Type" content="...; charset=...">.
    label = /<meta[^>]*?charset\s*=\s*["']?([^\s"'\/>;]+)/i.exec(bytes.subarray(0, 4096).toString('latin1'))?.[1];
    source = 'meta charset';
  }
  let decoder: TextDecoder;
  let note: string | undefined;
  try { decoder = new TextDecoder(label ?? 'utf-8'); } catch {
    decoder = new TextDecoder('utf-8');
    note = `unsupported charset label "${label}"; decoded as UTF-8`;
  }
  return { text: decoder.decode(bytes), encoding: { name: decoder.encoding, source: label && !note ? source : 'default', note } };
}

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

  async extractContent(options: ContentExtractionOptions & { budget?: CallBudget; windowMs?: number }): Promise<PageRead> {
    const call = options.budget ?? new CallBudget();
    // FA05: a page window opens when the page gets its first read slot; queueing only spends the call budget.
    let window: CallBudget | undefined;
    const active = () => window ?? call;
    const open = () => window ??= options.windowMs === undefined ? call
      : call.child(options.windowMs, `page read window exceeded (${options.windowMs} ms)`);
    const state: PageRead = {
      requestedUrl: options.url, status: 'not_attempted', attempts: [], content: '',
      maxContentLength: resolveContentLimit(options.maxContentLength),
      returnedLength: 0, truncated: false,
    };
    const attempt = async (transport: 'http' | 'browser'): Promise<boolean> => {
      const event: PageReadAttempt = { transport };
      const started = () => {
        active().remaining();
        // A started attempt owns the summary; earlier attempts keep their facts in the list.
        for (const key of ['httpStatus', 'contentType', 'finalUrl', 'pageTitle', 'encoding', 'error', 'originalLength'] as const) {
          delete state[key];
        }
        Object.assign(state, { status: 'not_attempted', content: '', returnedLength: 0, truncated: false });
        state.attempts.push(event);
      };
      const record = () => Object.assign(event, {
        status: state.httpStatus, outcome: state.status, contentType: state.contentType, finalUrl: state.finalUrl,
        encoding: state.encoding, originalLength: state.originalLength, returnedLength: state.originalLength === undefined ? undefined : state.returnedLength,
        truncated: state.truncated || undefined, error: state.error,
      });
      try {
        const text = transport === 'http'
          ? await this.browserPool.withHttp(() => {
              const budget = open();
              started();
              return this.extractWithAxios({ ...options, budget }, state);
            }, call)
          : await this.extractWithBrowser({ ...options, budget: open() }, state, started, event);
        if (state.status !== 'unsupported_media') {
          Object.assign(state, converting(() => truncateMarkdown(text, state.maxContentLength)));
          state.status = text.trim() ? 'text' : 'empty_text';
        }
        record();
        return ['text', 'unsupported_media'].includes(state.status);
      } catch (error) {
        const budget = active();
        const err = (budget.signal.aborted ? budget.signal.reason : error) as any;
        if (!state.attempts.includes(event)) {
          // Only queued, never started: the summary stays the last started attempt's.
          if (state.attempts.length) state.notStarted = { transport, reason: sanitizeErrorMessage(err) };
          else Object.assign(state, { status: 'not_attempted', error: sanitizeErrorMessage(err) });
          return false;
        }
        const response = err.response;
        if (response) {
          state.httpStatus = response.status;
          state.contentType = response.headers?.['content-type'];
          state.finalUrl = response.request?.res?.responseUrl;
        }
        state.error = sanitizeErrorMessage(err);
        if (state.status !== 'unsupported_media') {
          state.status = budget.signal.aborted && err.code !== 'ETIMEDOUT' ? 'cancelled'
            : err.code === 'ERR_CANCELED' ? 'cancelled'
            : ['ECONNABORTED', 'ETIMEDOUT'].includes(err.code) || err.name === 'TimeoutError' ? 'timeout'
            : err.reason === 'conversion_error' ? 'conversion_error' : 'http_error';
        }
        record();
        return state.status === 'unsupported_media';
      }
    };
    try {
      const complete = await attempt('http');
      if (!complete && !active().signal.aborted && !['cancelled', 'conversion_error'].includes(state.status)
        && (state.status === 'empty_text' || state.status === 'timeout'
          || [403, 429, 503].includes(state.httpStatus ?? 0))) {
        await attempt('browser');
      }
      if (state.status === 'text') delete state.error;
      return state;
    } finally {
      if (window && window !== call) window.dispose();
      if (!options.budget) call.dispose();
    }
  }

  private async extractWithAxios(options: ContentExtractionOptions & { budget: CallBudget }, state: PageRead): Promise<string> {
    const nominal = Math.min(options.timeout ?? OPERATION_TIMEOUTS.pageRequest, OPERATION_TIMEOUTS.pageRequest);
    const capMs = options.budget.timeout(nominal);
    // FA05: a total cap, not only axios's idle timeout. Axios drops abort reasons, so the timer stays local.
    // When the remaining budget is shorter, the call deadline itself ends the read and names the cause.
    const operation = new AbortController();
    const timer = nominal < options.budget.remaining() ? setTimeout(() => operation.abort(), capMs) : undefined;
    let response;
    try {
      response = await axios.get(options.url, {
        responseType: 'arraybuffer', signal: AbortSignal.any([options.budget.signal, operation.signal]), timeout: capMs,
        headers: { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36' },
        maxContentLength: READ_LIMIT_BYTES,
        validateStatus: status => status < 400,
      });
    } catch (error) {
      if (operation.signal.aborted && !options.budget.signal.aborted) {
        throw Object.assign(new Error(`HTTP page read exceeded its ${capMs} ms operation limit`), { code: 'ETIMEDOUT' });
      }
      // Over the read limit the headers were already received; keep them as facts.
      const received = (error as any)?.request?.res;
      if ((error as any)?.code !== 'ERR_BAD_RESPONSE' || !/maxContentLength/.test((error as any)?.message) || !received) throw error;
      state.httpStatus = received.statusCode;
      state.contentType = received.headers?.['content-type']?.toString();
      state.finalUrl = received.responseUrl ?? options.url;
      const limit = 'response body exceeds 10 MiB read limit';
      if (!SUPPORTED_MEDIA.includes(mediaType(state.contentType) ?? '')) {
        state.status = 'unsupported_media';
        throw new Error(`Unsupported media: ${state.contentType ?? 'unknown'} (${limit})`);
      }
      throw new Error(limit);
    } finally { if (timer) clearTimeout(timer); }
    state.httpStatus = response.status;
    state.contentType = response.headers['content-type']?.toString();
    state.finalUrl = response.request?.res?.responseUrl ?? options.url;
    return this.convertResponse(Buffer.from(response.data), state);
  }

  private convertResponse(bytes: Buffer, state: PageRead): string {
    const media = mediaType(state.contentType);
    if (bytes.subarray(0, 5).toString('ascii') === '%PDF-' || !SUPPORTED_MEDIA.includes(media ?? '')) {
      state.status = 'unsupported_media';
      state.error = `Unsupported media: ${state.contentType ?? 'unknown'}`;
      return '';
    }
    const { text, encoding } = decodeBody(bytes, state.contentType, media !== 'text/plain');
    state.encoding = encoding;
    if (media === 'text/plain') return text.replace(/\r\n?/g, '\n').trim();
    return converting(() => {
      state.pageTitle = documentTitle(cheerio.load(text));
      return this.parseContent(text, state.finalUrl);
    });
  }

  private async extractWithBrowser(
    options: ContentExtractionOptions & { budget: CallBudget }, state: PageRead, started: () => void,
    event: PageReadAttempt,
  ): Promise<string> {
    // The attempt starts when the launch or context creation begins, even if no page follows (FA07).
    return this.browserPool.withPage(async page => {
      // Main-frame navigation facts survive a navigation that turns into a download.
      let observed: Response | undefined;
      let downloadStarted = false;
      const onResponse = (candidate: Response) => {
        try {
          if (candidate.request().isNavigationRequest() && candidate.frame() === page.mainFrame()) observed = candidate;
        } catch { /* Not a navigation of this page. */ }
      };
      const onDownload = (download: { cancel(): Promise<void> }) => {
        downloadStarted = true;
        void download.cancel().catch(() => undefined);
      };
      page.on('response', onResponse);
      page.on('download', onDownload);
      let response: Response | null;
      try {
        response = await page.goto(options.url, {
          waitUntil: 'domcontentloaded', timeout: options.budget.timeout(OPERATION_TIMEOUTS.pageRequest),
        });
      } catch (error) {
        const unsupported = observed && !SUPPORTED_MEDIA.includes(mediaType(observed.headers()['content-type']) ?? '');
        if (!unsupported && !downloadStarted) throw error;
        state.finalUrl = observed?.url();
        state.httpStatus = observed?.status();
        state.contentType = observed?.headers()['content-type'];
        state.status = 'unsupported_media';
        state.error = `Unsupported media: ${state.contentType ?? 'unknown'}${observed ? '' : ' (download started)'}`;
        return '';
      } finally {
        page.off('response', onResponse);
        page.off('download', onDownload);
      }
      state.finalUrl = page.url();
      state.httpStatus = response?.status();
      state.contentType = response?.headers()['content-type'];
      if (state.httpStatus !== undefined && state.httpStatus >= 400) {
        throw new Error(`HTTP ${state.httpStatus}`);
      }
      const media = mediaType(state.contentType);
      if (!SUPPORTED_MEDIA.includes(media ?? '')) {
        state.status = 'unsupported_media';
        state.error = `Unsupported media: ${state.contentType ?? 'unknown'}`;
        return '';
      }
      const settle = media === 'text/plain' ? undefined : await this.settleRendering(page, options.budget);
      state.pageTitle = singleLine(await boundedRead(page.title(), options.budget, 'page.title()')) || undefined;
      const text = media === 'text/plain' ? await boundedRead(page.locator('body').innerText(), options.budget, 'body innerText')
        : await boundedRead(page.content(), options.budget, 'page.content()').then(html => converting(() => this.parseContent(html, state.finalUrl)));
      if (settle) event.renderWaitMs = settle.waitedMs;
      if (settle && !text.trim()) {
        state.error = `No visible text after waiting ${settle.waitedMs} ms for client rendering (limit ${settle.limitMs} ms)`;
      }
      return text;
    }, options.budget, started);
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
      // Candidates past targetCount stay in place, unread (R05: no candidate disappears).
      return await Promise.all(results.map(async (result, index) => index >= targetCount ? { ...result } : {
        ...result,
        read: await this.extractContent({ url: result.url, maxContentLength, budget, windowMs: OPERATION_TIMEOUTS.pageTotal }),
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
    return trimLineEnds(children(root)).replace(/\n{3,}/g, '\n\n').trim();
  }
}
