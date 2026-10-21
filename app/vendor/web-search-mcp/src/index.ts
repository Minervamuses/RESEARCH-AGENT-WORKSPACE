#!/usr/bin/env node
console.log('Web Search MCP Server starting...');

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { SearchEngine } from './search-engine.js';
import { EnhancedContentExtractor } from './enhanced-content-extractor.js';
import { WebSearchToolInput, WebSearchToolOutput, SearchResult } from './types.js';
import { formatSearchResponse, formatPageRead, parseInteger, parseBoolean, resolveContentLimit, validateSearchInput } from './utils.js';

class WebSearchMCPServer {
  private server: McpServer;
  private searchEngine: SearchEngine;
  private contentExtractor: EnhancedContentExtractor;

  constructor() {
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
      async (args: unknown) => {
        console.log(`[MCP] Tool call received: full-web-search`);
        console.log(`[MCP] Raw arguments:`, JSON.stringify(args, null, 2));

        try {
          // Convert and validate arguments
          const validatedArgs = this.validateAndConvertArgs(args);
          
          console.log(`[MCP] Validated args:`, JSON.stringify(validatedArgs, null, 2));
          
          console.log(`[MCP] Starting web search...`);
          const result = await this.handleWebSearch(validatedArgs);
          
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
      }
    );

    // Register the lightweight web search summaries tool (secondary choice for quick results)
    this.server.tool(
      'get-web-search-summaries',
      'Search the web and return only the search result snippets/descriptions without following links to extract full page content. This is a lightweight alternative to full-web-search for when you only need brief search results. Use full-web-search to read pages. Use citation_workflow for paper discovery, bibliographic metadata, abstracts and citations.',
      {
        query: z.string().describe('Search query to execute (lightweight alternative)'),
        limit: z.union([z.number(), z.string()]).transform(val => parseInteger(val, 'limit', 1, 10)).default(5).describe('Number of search results to return (1-10)'),
      },
      async (args: unknown) => {
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
          
          try {
            // Use existing search engine to get results with snippets
            const searchResponse = await this.searchEngine.search({
              query: obj.query,
              numResults: limit,
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
          } finally {
            // Ensure browsers are cleaned up after search-only operations
            // This prevents EventEmitter memory leaks when browsers accumulate listeners
            try {
              await this.searchEngine.closeAll();
            } catch (cleanupError) {
              console.error(`[MCP] Error during browser cleanup:`, cleanupError);
            }
          }
        } catch (error) {
          console.error(`[MCP] Error in get-web-search-summaries tool handler:`, error);
          throw error;
        }
      }
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
      async (args: unknown) => {
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
      }
    );
  }

  private validateAndConvertArgs(args: unknown): WebSearchToolInput {
    return validateSearchInput(args);
  }

  private async handleWebSearch(input: WebSearchToolInput): Promise<WebSearchToolOutput> {
    const startTime = Date.now();
    const { query, limit = 5, includeContent = true, maxContentLength } = input;
    
    console.error(`[web-search-mcp] DEBUG: handleWebSearch called with limit=${limit}, includeContent=${includeContent}`);

    try {
      const searchResponse = await this.searchEngine.search({ query, numResults: limit });
      const enhancedResults = includeContent
        ? await this.contentExtractor.extractContentForResults(searchResponse.results, limit, maxContentLength)
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

  private setupGracefulShutdown(): void {
    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason, promise) => {
      console.error('Unhandled Rejection at:', promise, 'reason:', reason);
      // Don't exit on unhandled rejections, just log them
    });

    // Handle uncaught exceptions
    process.on('uncaughtException', (error) => {
      console.error('Uncaught Exception:', error);
      // Don't exit on uncaught exceptions in MCP context
    });

    // Graceful shutdown - close browsers when process exits
    process.on('SIGINT', async () => {
      console.log('Shutting down gracefully...');
      try {
        await Promise.all([
          this.contentExtractor.closeAll(),
          this.searchEngine.closeAll()
        ]);
      } catch (error) {
        console.error('Error during graceful shutdown:', error);
      }
      process.exit(0);
    });

    process.on('SIGTERM', async () => {
      console.log('Shutting down gracefully...');
      try {
        await Promise.all([
          this.contentExtractor.closeAll(),
          this.searchEngine.closeAll()
        ]);
      } catch (error) {
        console.error('Error during graceful shutdown:', error);
      }
      process.exit(0);
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
