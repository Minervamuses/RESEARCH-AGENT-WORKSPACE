export type PageReadStatus = 'not_attempted' | 'http_error' | 'timeout' | 'cancelled'
  | 'unsupported_media' | 'conversion_error' | 'empty_text' | 'text';

/** The facts of one started read attempt; later attempts never overwrite them. */
export interface PageReadAttempt {
  transport: 'http' | 'browser';
  /** HTTP status of this attempt's response. */
  status?: number;
  outcome?: PageReadStatus;
  contentType?: string;
  finalUrl?: string;
  encoding?: PageRead['encoding'];
  /** Browser reads: how long the client-render wait lasted (FA04). */
  renderWaitMs?: number;
  originalLength?: number;
  returnedLength?: number;
  truncated?: boolean;
  error?: string;
}

export interface PageRead {
  requestedUrl: string;
  finalUrl?: string;
  pageTitle?: string;
  httpStatus?: number;
  contentType?: string;
  /** HTTP reads only: the decoder used and how it was chosen (FA03). */
  encoding?: { name: string; source: 'BOM' | 'Content-Type charset' | 'meta charset' | 'default'; note?: string };
  status: PageReadStatus;
  /** Started attempts only (FA07); the summary fields above describe the last of them. */
  attempts: PageReadAttempt[];
  /** A fallback that only queued and never started is not an attempt; its reason is kept here. */
  notStarted?: { transport: 'http' | 'browser'; reason: string };
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
  /** True once a page lease started for this engine (FA07); attempts counts those starts. */
  attempted: boolean;
  attempts: number;
  parsedCount: number;
  status: 'completed' | 'zero_parsed' | 'error' | 'not_attempted';
  reason?: 'deadline' | 'cancelled' | 'rate_limited' | 'queue_expired';
  /** Observed facts of the engine's search navigation. */
  httpStatus?: number;
  finalPath?: string;
  error?: string;
}

// Search results retain per-engine execution facts independently of page reads.
export interface SearchResultWithMetadata {
  results: SearchResult[];
  engines: SearchEngineState[];
}
