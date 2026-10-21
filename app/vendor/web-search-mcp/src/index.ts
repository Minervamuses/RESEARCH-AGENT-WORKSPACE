#!/usr/bin/env node
console.log('Web Search MCP Server starting...');

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { CallBudget, configuredTimeout, cleanupReserve, sharedBrowserPool } from './browser-pool.js';
import { SearchEngine } from './search-engine.js';
import { EnhancedContentExtractor } from './enhanced-content-extractor.js';
import { WebSearchToolInput, WebSearchToolOutput } from './types.js';
import { formatSearchResponse, formatPageRead, parseInteger, parseBoolean, resolveContentLimit, validateSearchInput } from './utils.js';

class WebSearchMCPServer {
  private server: McpServer;
  private searchEngine: SearchEngine;
  private contentExtractor: EnhancedContentExtractor;
  private activeBudgets = new Set<CallBudget>();
  private shuttingDown?: Promise<void>;

  constructor() {
    configuredTimeout();
    resolveContentLimit();
    this.server = new McpServer({
      name: 'web-search-mcp',
      version: '0.3.1',
    });

    this.searchEngine = new SearchEngine();
    this.contentExtractor = new EnhancedContentExtractor();

    this.setupTools();
    this.setupGracefulShutdown();
  }

  private setupTools(): void {
    // Register the main web search tool (primary choice for comprehensive searches)
    this.server.tool(
      'full-web-search',
      'Search the web and by default read top candidates as conservative Markdown, up to 10000 Unicode code points per page. Failed, unsupported or truncated pages are reported; search snippets remain separate. Use get-web-search-summaries for snippets only. Use citation_workflow for paper discovery, bibliographic metadata, abstracts and citations.',
      {
        query: z.string().describe('Search query to execute (recommended for comprehensive research)'),
        limit: z.union([z.number(), z.string()]).transform(val => parseInteger(val, 'limit', 1, 10)).default(5).describe('Number of fixed candidates to return (1-10)'),
        includeContent: z.union([z.boolean(), z.string()]).transform(parseBoolean).default(true)
          .describe('Whether to read page content (default true)'),
        maxContentLength: z.union([z.number(), z.string()]).transform(resolveContentLimit).optional()
          .describe('Per-page Markdown Unicode code point limit, 1–10000; omitted or 0 uses MAX_CONTENT_LENGTH (default 10000). Truncation is reported; metadata is excluded.'),
      },
      async (args: unknown, extra) => this.withBudget(extra, async budget => {
        console.log(`[MCP] Tool call received: full-web-search`);
        console.log(`[MCP] Raw arguments:`, JSON.stringify(args, null, 2));

        try {
          // Convert and validate arguments
          const validatedArgs = this.validateAndConvertArgs(args);
          
          console.log(`[MCP] Validated args:`, JSON.stringify(validatedArgs, null, 2));
          
          console.log(`[MCP] Starting web search...`);
          const result = await this.handleWebSearch(validatedArgs, budget);
          
          console.log(`[MCP] Search completed, found ${result.results.length} results`);
          
          const responseText = formatSearchResponse(
            result.query, result.results, result.engines ?? [], validatedArgs.includeContent,
          );

          return {
            content: [
              {
                type: 'text' as const,
                text: responseText,
              },
            ],
          };
        } catch (error) {
          console.error(`[MCP] Error in tool handler:`, error);
          throw error;
        }
      })
    );

    // Register the lightweight web search summaries tool (secondary choice for quick results)
    this.server.tool(
      'get-web-search-summaries',
      'Search the web and return only the search result snippets/descriptions without following links to extract full page content. This is a lightweight alternative to full-web-search for when you only need brief search results. Use full-web-search to read pages. Use citation_workflow for paper discovery, bibliographic metadata, abstracts and citations.',
      {
        query: z.string().describe('Search query to execute (lightweight alternative)'),
        limit: z.union([z.number(), z.string()]).transform(val => parseInteger(val, 'limit', 1, 10)).default(5).describe('Number of search results to return (1-10)'),
      },
      async (args: unknown, extra) => this.withBudget(extra, async budget => {
        console.log(`[MCP] Tool call received: get-web-search-summaries`);
        console.log(`[MCP] Raw arguments:`, JSON.stringify(args, null, 2));

        try {
          // Validate arguments
          if (typeof args !== 'object' || args === null) {
            throw new Error('Invalid arguments: args must be an object');
          }
          const obj = args as Record<string, unknown>;
          
          if (!obj.query || typeof obj.query !== 'string') {
            throw new Error('Invalid arguments: query is required and must be a string');
          }

          const limit = obj.limit === undefined ? 5 : parseInteger(obj.limit, 'limit', 1, 10);

          console.log(`[MCP] Starting web search summaries...`);
          
          // Use existing search engine to get results with snippets
          const searchResponse = await this.searchEngine.search({
            query: obj.query,
            numResults: limit,
            budget,
          });

          const responseText = formatSearchResponse(
            obj.query, searchResponse.results, searchResponse.engines,
          );

          return {
            content: [
              {
                type: 'text' as const,
                text: responseText,
              },
            ],
          };
        } catch (error) {
          console.error(`[MCP] Error in get-web-search-summaries tool handler:`, error);
          throw error;
        }
      })
    );

    // Register the single page content extraction tool
    this.server.tool(
      'get-single-web-page-content',
      'Read a provided web page URL as conservative Markdown, up to 10000 Unicode code points. Report failures and truncation without treating search snippets as page content. Use citation_workflow for paper discovery, bibliographic metadata, abstracts and citations.',
      {
        url: z.string().url().describe('The URL of the web page to extract content from'),
        maxContentLength: z.union([z.number(), z.string()]).transform(resolveContentLimit).optional()
          .describe('Markdown Unicode code point limit 1–10000; omitted or 0 uses MAX_CONTENT_LENGTH (default 10000). Metadata and truncation marker are excluded.'),
      },
      async (args: unknown, extra) => this.withBudget(extra, async budget => {
        console.log(`[MCP] Tool call received: get-single-web-page-content`);
        console.log(`[MCP] Raw arguments:`, JSON.stringify(args, null, 2));

        try {
          // Validate arguments
          if (typeof args !== 'object' || args === null) {
            throw new Error('Invalid arguments: args must be an object');
          }
          const obj = args as Record<string, unknown>;
          
          if (!obj.url || typeof obj.url !== 'string') {
            throw new Error('Invalid arguments: url is required and must be a string');
          }

          const maxContentLength = resolveContentLimit(obj.maxContentLength);

          console.log(`[MCP] Starting single page content extraction for: ${obj.url}`);
          
          // Use existing content extractor to get page content
          const pageRead = await this.contentExtractor.extractContent({
            url: obj.url,
            maxContentLength,
            budget,
          });

          const responseText = formatPageRead(pageRead);

          return {
            content: [
              {
                type: 'text' as const,
                text: responseText,
              },
            ],
          };
        } catch (error) {
          console.error(`[MCP] Error in get-single-web-page-content tool handler:`, error);
          throw error;
        }
      })
    );
  }

  private async withBudget<T>(
    extra: { signal?: AbortSignal; _meta?: Record<string, unknown> },
    fn: (budget: CallBudget) => Promise<T>,
  ): Promise<T> {
    const total = configuredTimeout();
    const remaining = extra._meta?.web_search_work_ms;
    const work = total - cleanupReserve(total);
    const duration = typeof remaining === 'number' && Number.isFinite(remaining)
      ? Math.max(0, Math.min(work, remaining)) : work;
    const budget = new CallBudget(duration, extra.signal);
    this.activeBudgets.add(budget);
    try { return await fn(budget); }
    finally { budget.dispose(); this.activeBudgets.delete(budget); }
  }

  private validateAndConvertArgs(args: unknown): WebSearchToolInput {
    return validateSearchInput(args);
  }

  private async handleWebSearch(input: WebSearchToolInput, budget: CallBudget): Promise<WebSearchToolOutput> {
    const startTime = Date.now();
    const { query, limit = 5, includeContent = true, maxContentLength } = input;
    
    console.error(`[web-search-mcp] DEBUG: handleWebSearch called with limit=${limit}, includeContent=${includeContent}`);

    try {
      const searchResponse = await this.searchEngine.search({ query, numResults: limit, budget });
      const enhancedResults = includeContent
        ? await this.contentExtractor.extractContentForResults(searchResponse.results, limit, maxContentLength, budget)
        : searchResponse.results;

      const searchTime = Date.now() - startTime;

      return {
        results: enhancedResults,
        total_results: enhancedResults.length,
        search_time_ms: searchTime,
        query,
        engines: searchResponse.engines,
      };
    } catch (error) {
      console.error('Web search error:', error);
      throw new Error(`Web search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private shutdown(): Promise<void> {
    if (this.shuttingDown) return this.shuttingDown;
    this.shuttingDown = (async () => {
      for (const budget of this.activeBudgets) budget.abort();
      try { await sharedBrowserPool.closeAll(); }
      catch (error) { console.error('Shutdown cleanup:', error); }
    })();
    return this.shuttingDown;
  }

  private setupGracefulShutdown(): void {
    const stop = () => { void this.shutdown().finally(() => process.exit(0)); };
    process.stdin.once('end', stop);
    process.stdin.once('close', stop);
    process.once('SIGINT', stop);
    process.once('SIGTERM', stop);
    process.once('uncaughtException', error => {
      console.error('Uncaught exception:', error);
      void this.shutdown().finally(() => process.exit(1));
    });
    process.once('unhandledRejection', error => {
      console.error('Unhandled rejection:', error);
      void this.shutdown().finally(() => process.exit(1));
    });
  }

  async run(): Promise<void> {
    console.log('Setting up MCP server...');
    const transport = new StdioServerTransport();
    
    console.log('Connecting to transport...');
    await this.server.connect(transport);
    console.log('Web Search MCP Server started');
    console.log('Server timestamp:', new Date().toISOString());
    console.log('Waiting for MCP messages...');
  }
}

// Start the server
const server = new WebSearchMCPServer();
server.run().catch((error: unknown) => {
  if (error instanceof Error) {
    console.error('Server error:', error.message);
  } else {
    console.error('Server error:', error);
  }
  process.exit(1);
});
