"""Provider clients for citation discovery and DOI verification.

Structured providers (Crossref, OpenAlex, doi.org) share the process-level
TTL cache and rate limiters defined in :mod:`citation.providers.net`; the
web MCP adapter reuses the chat session's already-loaded MCP tool handles.
"""
