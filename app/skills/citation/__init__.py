"""The built-in citation skill: bundle root and importable engine.

This directory is simultaneously the ``citation`` skill bundle (``SKILL.md``
+ ``manifest.yaml``) and the ``skills.citation`` package holding its engine:
a session-scoped :class:`skills.citation.service.CitationService`
(driven by the skill-only ``citation_workflow`` tool) over a process-scoped
:class:`skills.citation.hub.CitationProviderHub` that owns the shared
provider clients, cache, and rate limiters.

Search is stateless across Crossref, DataCite, and optional OpenAlex. Saving
freshly resolves a self-contained WorkIntent and re-verifies its DOI against
doi.org's CSL JSON record (or an official authority record for arXiv and
NeurIPS). In a desktop project the verified work is merged into the project
CSL-JSON bibliography, the only citation store, and is citable only once it
is there; the CLI has no bibliography, so a save there is verified for the
current task only and writes nothing. Verification is strictly
identity-level: a citable verification level means the canonical identity and
bibliographic record agree, never that the source supports a claim.

Nothing here fabricates bibliographic data: failed lookups and bibliography
write failures fail closed, and a failed work is not citable.
"""

__all__ = ["SKILL_NAME"]

# The skill bundle's frontmatter name; the session keys its citation-specific
# behavior (thinking isolation, teardown, gate policy) on this.
SKILL_NAME = "citation"
