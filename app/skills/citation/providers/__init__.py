"""Provider clients for citation discovery and DOI verification.

Crossref, DataCite, OpenAlex, and doi.org share the process-level TTL cache
and rate limiters defined in :mod:`citation.providers.net`.
"""
from skills.citation.providers.datacite import DataCiteClient

__all__ = ["DataCiteClient"]
