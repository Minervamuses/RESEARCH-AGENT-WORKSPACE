import type { SearchResult, SearchEngineState, WebSearchToolInput, PageRead } from './types.js';

/**
 * Utility functions for the web search MCP server
 */

export function sanitizeQuery(query: string): string {
  return query.trim().substring(0, 1000); // Limit query length
}

/** Agent-visible facts shared by both search tools; importing this never starts stdio. */
export function formatSearchResponse(
  query: string, results: SearchResult[], engines: SearchEngineState[], includeContent = false,
): string {
  const lines = [`Search for "${query}": ${results.length} candidates`, 'Engine execution:'];
  for (const engine of engines) {
    // New facts follow status= so the existing line prefix stays the same; the free-text error stays last.
    const facts = [
      engine.reason && `reason=${engine.reason}`,
      engine.httpStatus !== undefined && `http_status=${engine.httpStatus}`,
      engine.finalPath && `final_path=${engine.finalPath}`,
      engine.error && `error=${engine.error}`,
    ].filter(Boolean).map(fact => `; ${fact}`).join('');
    lines.push(`- ${engine.name}: attempted=${engine.attempted}; attempts=${engine.attempts}; parsed_count=${engine.parsedCount}; status=${engine.status}${facts}`);
  }
  if (!results.length) {
    const ran = engines.filter(e => ['completed', 'zero_parsed', 'error'].includes(e.status));
    const reasons = [...new Set(engines.map(e => e.reason).filter(Boolean))].join(', ');
    lines.push(!ran.length ? `No engine was attempted in this call (${reasons || 'unknown reason'}); no candidates are available.`
      : ran.every(e => e.status === 'error') ? 'All attempted engines failed; no candidates are available.'
      : ran.every(e => e.status !== 'error') ? 'No candidates parsed in this call; this is not evidence of no matching pages.'
      : 'Some engines failed and the others parsed no candidates; this is not evidence of no matching pages.');
  }
  results.forEach((result, index) => {
    lines.push('', `**${index + 1}. Search title: ${result.title}**`, `URL: ${result.url}`);
    const link = result.resolution;
    if (link?.outcome === 'resolved') {
      lines.push(`Link: engine redirect from ${new URL(link.wrapperUrl).host} resolved by navigation in ${link.ms} ms`);
    } else if (link) {
      lines.push(`Link: engine redirect not resolved (${link.outcome}${link.reason ? `: ${link.reason}` : ''}); this URL is the engine's redirect wrapper, not the source page`);
    }
    lines.push(`Search snippet: ${result.description}`,
      `Source engines: ${(result.sourceEngines ?? []).join(', ')}`,
      `Read status: ${result.read?.status ?? 'not_attempted'}`);
    if (includeContent && result.read) lines.push(formatPageRead(result.read));
  });
  const counts: Record<string, number> = {};
  let attempts = 0, http = 0, browser = 0, started = 0;
  for (const result of results) {
    const status = result.read?.status ?? 'not_attempted';
    counts[status] = (counts[status] ?? 0) + 1;
    const events = result.read?.attempts ?? [];
    attempts += events.length;
    http += events.filter(a => a.transport === 'http').length;
    browser += events.filter(a => a.transport === 'browser').length;
    if (events.length) started++;
  }
  const redirects = results.filter(result => result.resolution);
  const resolved = redirects.filter(result => result.resolution!.outcome === 'resolved').length;
  lines.push('', `Read statistics: selected=${results.length}; candidates_attempted=${started}; source_read_attempts=${attempts}; http_attempts=${http}; browser_attempts=${browser}; returned=${results.length}; states=${JSON.stringify(counts)}; engine_redirects_resolved=${resolved}; engine_redirects_unresolved=${redirects.length - resolved}`,
    // FA08: the counting rules travel with the numbers.
    'Statistics scope: source_read_attempts counts started HTTP and browser reads (a request sent, or a browser launch or context begun); reads that only queued are not counted. candidates_attempted counts candidates with at least one started read. Redirects followed within one HTTP read are not counted separately. parsed_count is the rows an engine returned before cross-engine deduplication and the limit. engine_redirects_resolved/unresolved count candidates whose search link was an engine redirect wrapper.');
  return lines.join('\n');
}

export function parseInteger(value: unknown, name: string, min: number, max: number): number {
  const converted = typeof value === 'string' && /^\d+$/.test(value.trim())
    ? Number(value.trim()) : value;
  if (typeof converted !== 'number' || !Number.isSafeInteger(converted) || converted < min || converted > max) {
    throw new Error(`Invalid ${name}: must be an integer between ${min} and ${max}`);
  }
  return converted;
}

export function parseBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string' && /^(true|false)$/i.test(value)) return value.toLowerCase() === 'true';
  throw new Error('Invalid includeContent: must be true or false');
}

export function resolveContentLimit(value?: unknown): number {
  const deployed = process.env.MAX_CONTENT_LENGTH === undefined
    ? 10000 : parseInteger(process.env.MAX_CONTENT_LENGTH, 'MAX_CONTENT_LENGTH', 1, 10000);
  if (value === undefined) return deployed;
  const explicit = parseInteger(value, 'maxContentLength', 0, 10000);
  return explicit === 0 ? deployed : explicit;
}

/** Query and limit rules shared by both search tools. */
export function validateSearchQuery(args: unknown): { query: string; limit: number } {
  if (typeof args !== 'object' || args === null) throw new Error('Invalid arguments: expected object');
  const obj = args as Record<string, unknown>;
  if (typeof obj.query !== 'string' || !obj.query.trim()) throw new Error('Invalid query: expected non-empty string');
  return { query: obj.query, limit: obj.limit === undefined ? 5 : parseInteger(obj.limit, 'limit', 1, 10) };
}

export function validateSearchInput(args: unknown): WebSearchToolInput {
  const { query, limit } = validateSearchQuery(args);
  const obj = args as Record<string, unknown>;
  return {
    query, limit,
    includeContent: obj.includeContent === undefined ? true : parseBoolean(obj.includeContent),
    maxContentLength: resolveContentLimit(obj.maxContentLength),
  };
}

// Code points scanned on each side of a cut; at least the 10000 point content limit.
const LINK_SCAN = 10000;

/**
 * Moves a cut (in code points) back so that it never lands inside a [label](<url>) link or a bare
 * http(s) URL: a clipped destination would be a different, fabricated link. One bounded local scan.
 */
function safeCut(p: string[], cut: number): number {
  const low = Math.max(0, cut - LINK_SCAN), high = Math.min(p.length, cut + LINK_SCAN);
  const breaks = (ch?: string) => ch === undefined || ch === '<' || ch === '>' || /\s/.test(ch);
  const scheme = (i: number) => p[i] === 'h'
    && ['http://', 'https://'].some(prefix => Array.from(prefix).every((ch, k) => p[i + k] === ch));
  // The '[' that opens a label ending at `close`, balancing nested brackets such as [[1]].
  const labelStart = (close: number): number | undefined => {
    let depth = 0;
    for (let i = close; i >= low; i--) {
      if (p[i] === ']') depth++;
      else if (p[i] === '[' && --depth === 0) return i;
    }
    return undefined;
  };
  // End (exclusive) of a link whose label closes at i: "](<...>)" or "](http...".
  const linkEnd = (i: number): number | undefined => {
    if (p[i] !== ']' || p[i + 1] !== '(') return undefined;
    let close = i + 2;
    if (p[close] === '<') {
      while (close < high && p[close] !== '>') close++;
      return close + 2;
    }
    if (!scheme(close)) return undefined;
    while (close < high && !breaks(p[close])) close++;
    return close;
  };
  for (let i = cut - 1; i >= low; i--) {
    const end = linkEnd(i);
    if (end === undefined) continue;
    const start = cut < end ? labelStart(i) : undefined;
    if (start !== undefined) return start;
    break;
  }
  for (let i = cut; i < high; i++) {
    if (linkEnd(i) === undefined) continue;
    const start = labelStart(i);
    if (start !== undefined && start < cut) return start;
    break;
  }
  // A bare URL token around the cut is dropped from its scheme on.
  if (cut > 0 && !breaks(p[cut - 1]) && !breaks(p[cut])) {
    let token = cut;
    while (token > low && !breaks(p[token - 1])) token--;
    for (let i = cut - 1; i >= token; i--) if (scheme(i)) return i;
  }
  return cut;
}

export function truncateMarkdown(text: string, limit: number): {
  content: string; truncated: boolean; originalLength: number; returnedLength: number;
} {
  const points = Array.from(text);
  if (points.length <= limit) {
    return { content: text, truncated: false, originalLength: points.length, returnedLength: points.length };
  }
  const boundary = safeCut(points, limit);
  return { content: points.slice(0, boundary).join(''), truncated: true, originalLength: points.length, returnedLength: boundary };
}

/** One short line for the Agent: no ANSI escapes, no Playwright call log, first line kept. */
export function sanitizeErrorMessage(error: unknown): string {
  const text = (error instanceof Error ? error.message : String(error)).replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
  const reason = text.split(/\n\s*Call log:/)[0].split('\n').map(line => line.trim()).find(Boolean) ?? '';
  return Array.from(reason).length > 300 ? `${Array.from(reason).slice(0, 300).join('')}…` : reason;
}

export function formatPageRead(read: PageRead): string {
  const lines = [
    `Requested URL: ${read.requestedUrl}`,
    `Final URL: ${read.finalUrl ?? 'unknown'}`,
    `Page title: ${read.pageTitle ?? 'unknown'}`,
    `HTTP status: ${read.httpStatus ?? 'unknown'}; Content-Type: ${read.contentType ?? 'unknown'}`,
  ];
  if (read.encoding) {
    lines.push(`Character encoding: ${read.encoding.name} (${read.encoding.source}${read.encoding.note ? `; ${read.encoding.note}` : ''})`);
  }
  lines.push(`Page read status: ${read.status}; attempts=${read.attempts.length}`);
  for (const event of read.attempts) {
    const facts = [
      event.outcome && `read_status=${event.outcome}`,
      event.contentType && `content_type=${event.contentType}`,
      event.finalUrl && `final_url=${event.finalUrl}`,
      event.encoding && `encoding=${event.encoding.name}`,
      event.renderWaitMs !== undefined && `render_wait_ms=${event.renderWaitMs}`,
      event.originalLength !== undefined && `markdown_length=${event.returnedLength}/${event.originalLength}`,
      event.truncated && 'truncated=true',
      event.error && `error=${event.error}`,
    ].filter(Boolean).map(fact => `; ${fact}`).join('');
    lines.push(`- ${event.transport}: status=${event.status ?? 'unknown'}${facts}`);
  }
  if (read.notStarted) lines.push(`- ${read.notStarted.transport}: not started (${read.notStarted.reason})`);
  if (read.error) lines.push(`Read error: ${read.error}`);
  if (read.originalLength !== undefined) {
    lines.push(`Markdown length: returned=${read.returnedLength}; original=${read.originalLength}; limit=${read.maxContentLength} Unicode code points`);
  }
  if (read.content) lines.push('', '**Page content:**', read.content);
  if (read.truncated) {
    lines.push(`[Content truncated: ${read.returnedLength} of ${read.originalLength ?? 'unknown'} Unicode code points delivered; limit=${read.maxContentLength}; remainder not delivered]`);
  }
  return lines.join('\n');
}
