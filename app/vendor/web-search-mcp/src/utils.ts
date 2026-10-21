import type { SearchResult, SearchEngineState } from './types.js';

/**
 * Utility functions for the web search MCP server
 */

export function cleanText(text: string, maxLength: number = 10000): string {
  return text
    .replace(/\s+/g, ' ') // Replace multiple whitespace with single space
    .replace(/\n\s*\n/g, '\n') // Replace multiple newlines with single newline
    .trim()
    .substring(0, maxLength);
}

export function getWordCount(text: string): number {
  return text.trim().split(/\s+/).filter(word => word.length > 0).length;
}

export function getContentPreview(text: string, maxLength: number = 500): string {
  const cleaned = cleanText(text, maxLength);
  return cleaned.length === maxLength ? cleaned + '...' : cleaned;
}

export function generateTimestamp(): string {
  return new Date().toISOString();
}

export function validateUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function sanitizeQuery(query: string): string {
  return query.trim().substring(0, 1000); // Limit query length
}

export function getRandomUserAgent(): string {
  const userAgents = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
  ];
  return userAgents[Math.floor(Math.random() * userAgents.length)];
}

export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export function isPdfUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.pathname.toLowerCase().endsWith('.pdf');
  } catch {
    // If URL parsing fails, check the raw string as fallback
    return url.toLowerCase().endsWith('.pdf');
  }
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
    lines.push('', `**${index + 1}. Search title: ${result.title}**`,
      `URL: ${result.url}`, `Search snippet: ${result.description}`,
      `Source engines: ${(result.sourceEngines ?? []).join(', ')}`,
      `Read status: ${result.fetchStatus}`);
    if (result.error) lines.push(`Read error: ${result.error}`);
    if (includeContent && result.fullContent) lines.push('', '**Page content:**', result.fullContent);
  });
  return lines.join('\n');
}
