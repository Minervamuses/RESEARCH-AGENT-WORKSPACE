"""Versioned, exact-alias venue classification for citation discovery."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import yaml

from skills.citation.types import VenueAnnotation

_WS_RE = re.compile(r"\s+")


def normalize_venue_name(raw: str | None) -> str:
    """Normalize an explicit catalog alias; never perform fuzzy matching."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", html.unescape(raw)).casefold()
    text = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text)
    return _WS_RE.sub(" ", text).strip()


@dataclass(frozen=True)
class VenueCatalog:
    version: str
    source: str
    aliases: dict[str, VenueAnnotation]


@lru_cache(maxsize=1)
def load_venue_catalog() -> VenueCatalog:
    path = resources.files("skills.citation").joinpath("venue_catalog.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported citation venue catalog schema")
    version = str(payload.get("catalog_version", "")).strip()
    source = str(payload.get("source", "")).strip()
    if not version or not source:
        raise ValueError("venue catalog requires catalog_version and source")

    aliases: dict[str, VenueAnnotation] = {}
    for item in payload.get("venues", []):
        if not isinstance(item, dict):
            raise ValueError("venue catalog entries must be mappings")
        canonical = str(item.get("canonical_name", "")).strip()
        kind = str(item.get("kind", "")).strip()
        tier = item.get("tier")
        tier = str(tier).strip() if tier is not None else None
        if not canonical or not kind:
            raise ValueError("venue catalog entries require canonical_name and kind")
        annotation = VenueAnnotation(
            canonical_name=canonical,
            kind=kind,
            tier=tier or None,
            source=source,
            catalog_version=version,
        )
        raw_aliases = [canonical, *(item.get("aliases") or [])]
        for raw_alias in raw_aliases:
            key = normalize_venue_name(str(raw_alias))
            if not key:
                continue
            previous = aliases.get(key)
            if previous is not None and previous != annotation:
                raise ValueError(f"duplicate venue alias: {raw_alias!r}")
            aliases[key] = annotation
    return VenueCatalog(version=version, source=source, aliases=aliases)


def annotate_venue(raw: str | None) -> VenueAnnotation:
    catalog = load_venue_catalog()
    key = normalize_venue_name(raw)
    matched = catalog.aliases.get(key)
    if matched is not None:
        return matched
    return VenueAnnotation(
        canonical_name=(raw or "").strip(),
        kind="unclassified",
        tier=None,
        source=catalog.source,
        catalog_version=catalog.version,
    )
