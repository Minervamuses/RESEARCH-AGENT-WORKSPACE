"""The built-in citation skill: bundle root and importable engine.

This directory is simultaneously the ``citation`` skill bundle (``SKILL.md``
+ ``manifest.yaml``) and the ``skills.citation`` package holding its engine:
a session-scoped :class:`skills.citation.coordinator.CitationCoordinator`
(driven by the skill-only ``citation_workflow`` tool) over a process-scoped
:class:`skills.citation.hub.CitationProviderHub` that owns the shared
provider clients, cache, and rate limiters.

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

__all__ = ["SKILL_NAME", "__version__"]

# The skill bundle's frontmatter name; the session keys its citation-specific
# behavior (thinking isolation, teardown, gate policy) on this.
SKILL_NAME = "citation"

__version__ = "0.2.0"
