export type PageReadStatus = 'not_attempted' | 'http_error' | 'timeout' | 'cancelled'
  | 'unsupported_media' | 'conversion_error' | 'empty_text' | 'text';

export interface PageRead {
  requestedUrl: string;
  finalUrl?: string;
  pageTitle?: string;
  httpStatus?: number;
  contentType?: string;
  status: PageReadStatus;
  attempts: { transport: 'http' | 'browser'; status?: number; error?: string }[];
  content: string;
  maxContentLength: number;
  originalLength?: number;
  returnedLength: number;
  truncated: boolean;
  error?: string;
}

export interface SearchResult {
  title: string;
  url: string;
  description: string;
  fullContent: string;
  contentPreview: string;
  wordCount: number;
  timestamp: string;
  fetchStatus: 'success' | 'error' | 'timeout' | 'not_requested' | PageReadStatus;
  read?: PageRead;
  sourceEngines?: string[];
  observedUrl?: string;
  error?: string;
}

export interface SearchResponse {
  query: string;
  limit: number;
  results: SearchResult[];
  totalFound: number;
  searchTimestamp: string;
  processingTimeMs: number;
}

export interface SearchOptions {
  query: string;
  numResults?: number;
  timeout?: number;
}

export interface ContentExtractionOptions {
  url: string;
  timeout?: number;
  maxContentLength?: number;
}

export interface WebSearchToolInput {
  query: string;
  limit?: number;
  includeContent?: boolean;
  maxContentLength?: number;
}

export interface WebSearchToolOutput {
  results: SearchResult[];
  total_results: number;
  search_time_ms: number;
  query: string;
  status?: string;
  engines?: SearchEngineState[];
}

// New types for search summaries (snippets only)
export interface SearchSummaryResult {
  title: string;
  url: string;
  description: string;
  timestamp: string;
}

export interface SearchSummaryOutput {
  results: SearchSummaryResult[];
  total_results: number;
  search_time_ms: number;
  query: string;
}

// New types for single page content
export interface SinglePageContentOutput {
  url: string;
  title: string;
  content: string;
  contentPreview: string;
  wordCount: number;
  timestamp: string;
  fetchStatus: 'success' | 'error';
  error?: string;
}

export interface SearchEngineState {
  name: string;
  attempted: boolean;
  attempts: number;
  parsedCount: number;
  status: 'completed' | 'zero_parsed' | 'error' | 'strategy_stopped';
  error?: string;
}

// Search results retain per-engine execution facts independently of page reads.
export interface SearchResultWithMetadata {
  results: SearchResult[];
  engine: string;
  engines: SearchEngineState[];
}
