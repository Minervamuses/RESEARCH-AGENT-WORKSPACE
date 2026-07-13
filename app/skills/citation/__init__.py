"""The built-in citation skill: bundle root and importable engine.

This directory is simultaneously the ``citation`` skill bundle (``SKILL.md``
+ ``manifest.yaml``) and the ``skills.citation`` package holding its engine:
a session-scoped :class:`skills.citation.service.CitationService`
(driven by the skill-only ``citation_workflow`` tool) over a process-scoped
:class:`skills.citation.hub.CitationProviderHub` that owns the shared
provider clients, cache, and rate limiters.

Search is stateless across Crossref, DataCite, and optional OpenAlex. Saving
freshly resolves a self-contained WorkIntent and re-verifies its DOI via
doi.org (CSL JSON + BibTeX for the same
canonical DOI, validated through pybtex) and persists an atomic bundle
(``reference.bib`` + ``citation.json`` sidecar). Verification is strictly
identity-level: a citable verification level means the canonical identity and bibliographic
pipeline agree on the record, never that the source supports a claim.

Nothing here fabricates bibliographic data: failed lookups, DOI mismatches,
and storage conflicts fail closed and write nothing.
"""

__all__ = ["SKILL_NAME", "__version__"]

# The skill bundle's frontmatter name; the session keys its citation-specific
# behavior (thinking isolation, teardown, gate policy) on this.
SKILL_NAME = "citation"

__version__ = "0.3.0"
