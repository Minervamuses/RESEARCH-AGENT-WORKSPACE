"""Citation workflow package.

Session-scoped :class:`citation.coordinator.CitationCoordinator` (driven by
chat's ``/citation`` slash command) over a process-scoped
:class:`citation.hub.CitationProviderHub` that owns the shared provider
clients, cache, and rate limiters.

Discovery runs structured providers (Crossref, and OpenAlex when
``OPENALEX_API_KEY`` is set) fused by deterministic reciprocal-rank fusion,
with the web MCP only as an explicit or empty-result fallback. Confirmation
re-verifies the selected DOI via doi.org (CSL JSON + BibTeX for the same
canonical DOI, validated through pybtex) and persists an atomic bundle
(``reference.bib`` + ``citation.json`` sidecar). Verification is strictly
identity-level: ``identity_verified`` means the DOI and bibliographic
pipeline agree on the record, never that the source supports a claim.

Nothing here fabricates bibliographic data: failed lookups, DOI mismatches,
and storage conflicts fail closed and write nothing.
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
