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
    lines.push(`- ${engine.name}: attempted=${engine.attempted}; attempts=${engine.attempts}; parsed_count=${engine.parsedCount}; status=${engine.status}${engine.error ? `; error=${engine.error}` : ''}`);
  }
  if (!results.length) {
    lines.push(engines.every(e => e.status === 'error')
      ? 'All attempted engines failed; no candidates are available.'
      : 'No candidates parsed in this call; this is not evidence of no matching pages.');
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
  let attempts = 0, http = 0, browser = 0, retries = 0, started = 0;
  for (const result of results) {
    const status = result.read?.status ?? 'not_attempted';
    counts[status] = (counts[status] ?? 0) + 1;
    const events = result.read?.attempts ?? [];
    const httpCount = events.filter(a => a.transport === 'http').length;
    const browserCount = events.filter(a => a.transport === 'browser').length;
    attempts += events.length;
    http += httpCount;
    browser += browserCount;
    retries += Math.max(0, httpCount - 1) + Math.max(0, browserCount - 1);
    if (events.length) started++;
  }
  const redirects = results.filter(result => result.resolution);
  const resolved = redirects.filter(result => result.resolution!.outcome === 'resolved').length;
  lines.push('', `Read statistics: selected=${results.length}; candidates_attempted=${started}; source_read_attempts=${attempts}; http_attempts=${http}; browser_attempts=${browser}; transport_retries=${retries}; returned=${results.length}; states=${JSON.stringify(counts)}; engine_redirects_resolved=${resolved}; engine_redirects_unresolved=${redirects.length - resolved}`);
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

export function validateSearchInput(args: unknown): WebSearchToolInput {
  if (typeof args !== 'object' || args === null) throw new Error('Invalid arguments: expected object');
  const obj = args as Record<string, unknown>;
  if (typeof obj.query !== 'string' || !obj.query.trim()) throw new Error('Invalid query: expected non-empty string');
  return {
    query: obj.query,
    limit: obj.limit === undefined ? 5 : parseInteger(obj.limit, 'limit', 1, 10),
    includeContent: obj.includeContent === undefined ? true : parseBoolean(obj.includeContent),
    maxContentLength: resolveContentLimit(obj.maxContentLength),
  };
}

export function truncateMarkdown(text: string, limit: number): {
  content: string; truncated: boolean; originalLength: number; returnedLength: number;
} {
  const points = Array.from(text);
  let content = points.slice(0, limit).join('');
  let boundary = content.length;
  // A clipped destination would be a different, fabricated link. Omit that whole link.
  const links = /\[[^\]\n]*\]\((?:<[^>]*>|[^)\n]*)\)|https?:\/\/[^\s<>]+/g;
  for (const match of text.matchAll(links)) {
    if (match.index < boundary && boundary < match.index + match[0].length) {
      boundary = match.index;
      break;
    }
  }
  content = text.slice(0, boundary);
  return {
    content, truncated: content.length < text.length,
    originalLength: points.length, returnedLength: Array.from(content).length,
  };
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
    lines.push(`- ${event.transport}: status=${event.status ?? 'unknown'}${event.error ? `; error=${event.error}` : ''}`);
  }
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
