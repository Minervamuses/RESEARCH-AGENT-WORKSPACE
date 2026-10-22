export type PageReadStatus = 'not_attempted' | 'http_error' | 'timeout' | 'cancelled'
  | 'unsupported_media' | 'conversion_error' | 'empty_text' | 'text';

export interface PageRead {
  requestedUrl: string;
  finalUrl?: string;
  pageTitle?: string;
  httpStatus?: number;
  contentType?: string;
  /** HTTP reads only: the decoder used and how it was chosen (FA03). */
  encoding?: { name: string; source: 'BOM' | 'Content-Type charset' | 'meta charset' | 'default'; note?: string };
  status: PageReadStatus;
  attempts: { transport: 'http' | 'browser'; status?: number; error?: string }[];
  content: string;
  maxContentLength: number;
  originalLength?: number;
  returnedLength: number;
  truncated: boolean;
  error?: string;
}

export interface LinkResolution {
  /** Absolute engine redirect wrapper that was navigated (FA14). */
  wrapperUrl: string;
  outcome: 'resolved' | 'stayed_on_engine_host' | 'timeout' | 'failed' | 'not_started';
  ms?: number;
  reason?: string;
}

export interface SearchResult {
  title: string;
  url: string;
  description: string;
  read?: PageRead;
  sourceEngines?: string[];
  observedUrl?: string;
  resolution?: LinkResolution;
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
  query: string;
  engines?: SearchEngineState[];
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
  engines: SearchEngineState[];
}
