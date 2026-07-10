"""The /citation slash command: the only chat surface of the Coordinator.

Search, select, confirm, and bundle writing are reachable exclusively
through this handler — the Coordinator's mutating methods are never bound
into the model tool graph, and there is deliberately no /cite alias.
"""

from __future__ import annotations

from citation.coordinator import (
    CitationCoordinator,
    SearchOutcome,
    SelectOutcome,
)
from citation.types import CitationCandidate, CitationMatch, CitationResult, SourceRef

USAGE = (
    "usage: /citation <query> | search <query> | list [page] | show <candidate-id> | "
    "more [query] | select <candidate-id> | confirm <match-id> | status | cancel | "
    "sources [page] | source <source-id>"
)

_SUBCOMMANDS = {
    "search", "list", "show", "more", "select", "confirm",
    "status", "cancel", "sources", "source",
}


def _candidate_line(candidate: CitationCandidate) -> list[str]:
    lines = [f"[{candidate.candidate_id}] {candidate.short_label()}"]
    if candidate.doi:
        lines.append(f"      DOI: {candidate.doi}")
    if candidate.venue:
        lines.append(f"      venue: {candidate.venue}")
    providers = ", ".join(sorted(candidate.provider_ids))
    if providers:
        lines.append(f"      providers: {providers}")
    if candidate.related_group:
        lines.append(f"      related-version group: {candidate.related_group}")
    return lines


def format_candidates(
    candidates: list[CitationCandidate], *, page: int = 1, total_pages: int = 1
) -> str:
    if not candidates:
        return "no candidates"
    lines = [f"Candidates (page {page}/{total_pages}):"]
    for candidate in candidates:
        lines.extend(_candidate_line(candidate))
    lines.append(
        "Use /citation show <candidate-id> for details, "
        "/citation select <candidate-id> to resolve matches."
    )
    return "\n".join(lines)


def format_candidate_detail(candidate: CitationCandidate) -> str:
    lines = [f"Candidate {candidate.candidate_id} (workflow {candidate.workflow_id}):"]
    lines.append(f"  title: {candidate.title or '(unknown)'}")
    if candidate.authors:
        lines.append(f"  authors: {', '.join(candidate.authors)}")
    for label, value in (
        ("year", candidate.year),
        ("venue", candidate.venue),
        ("DOI", candidate.doi),
        ("URL", candidate.url),
        ("related-version group", candidate.related_group),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    if candidate.snippet:
        lines.append(f"  snippet: {candidate.snippet[:200]}")
    for provider, pid in sorted(candidate.provider_ids.items()):
        rank = candidate.provider_ranks.get(provider)
        lines.append(f"  provider {provider}: {pid} (rank {rank})")
    for field_name, provider in sorted(candidate.field_provenance.items()):
        lines.append(f"  provenance {field_name}: {provider}")
    for field_name, values in sorted(candidate.conflicts.items()):
        rendered = "; ".join(f"{v['provider']}={v['value']!r}" for v in values)
        lines.append(f"  conflict {field_name}: {rendered}")
    return "\n".join(lines)


def format_search_outcome(outcome: SearchOutcome, *, appended: bool = False) -> str:
    if outcome.error:
        return outcome.error
    lines = []
    verb = "appended" if appended else "found"
    lines.append(f"{verb} {len(outcome.candidates)} candidate(s)")
    if outcome.used_web_fallback:
        lines.append("(web search results included)")
    for state in outcome.provider_states:
        detail = f" — {state.detail}" if state.detail else ""
        lines.append(f"  provider {state.provider}: {state.status}{detail}")
    if outcome.candidates:
        lines.append("")
        lines.append(format_candidates(outcome.candidates))
    return "\n".join(lines)


def format_matches(matches: list[CitationMatch]) -> str:
    lines = ["Confirmable matches:"]
    for match in matches:
        lines.append(f"[{match.match_id}] DOI {match.canonical_doi}")
        if match.title:
            lines.append(f"      title: {match.title}")
        meta = []
        if match.year is not None:
            meta.append(str(match.year))
        if match.venue:
            meta.append(match.venue)
        if match.registration_agency:
            meta.append(f"RA: {match.registration_agency}")
        if meta:
            lines.append(f"      {' | '.join(meta)}")
    lines.append("Use /citation confirm <match-id> to verify and save.")
    return "\n".join(lines)


def format_result(result: CitationResult) -> str:
    lines = [f"citation {result.status}: {result.message}".rstrip(": ")]
    if result.source is not None:
        lines.append(f"  source: {result.source.source_id} ({result.source.verification_level})")
        lines.append(f"  cite with [[cite:{result.source.source_id}]]")
    if result.accepted_doi:
        lines.append(f"  DOI: {result.accepted_doi}")
    if result.bundle_path:
        lines.append(f"  bundle: {result.bundle_path}")
    if result.verification is not None:
        for warning in result.verification.warnings:
            lines.append(f"  warning: {warning}")
        for code in result.verification.codes:
            lines.append(f"  code: {code}")
        for check in result.verification.checks:
            if not check.passed:
                lines.append(f"  failed check: {check.name} ({check.detail})")
    return "\n".join(lines)


def format_sources(sources: list[SourceRef], *, page: int, total_pages: int) -> str:
    if not sources:
        return "no saved sources in this session"
    lines = [f"Sources (page {page}/{total_pages}):"]
    for ref in sources:
        label = ref.title or ref.doi or ref.url or "(unknown)"
        lines.append(f"[{ref.source_id}] {label}")
        meta = [ref.verification_level]
        if ref.doi:
            meta.append(f"DOI {ref.doi}")
        if ref.year:
            meta.append(str(ref.year))
        lines.append(f"      {' | '.join(meta)}")
    lines.append("Use /citation source <source-id> to re-activate one for citing.")
    return "\n".join(lines)


def format_source_detail(ref: SourceRef) -> str:
    lines = [f"Source {ref.source_id} re-activated:"]
    lines.append(f"  title: {ref.title or '(unknown)'}")
    if ref.authors:
        lines.append(f"  authors: {', '.join(ref.authors)}")
    for label, value in (
        ("year", ref.year), ("venue", ref.venue), ("DOI", ref.doi),
        ("URL", ref.url), ("bundle", ref.bundle_path),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    lines.append(f"  verification: {ref.verification_level}")
    lines.append(f"  cite with [[cite:{ref.source_id}]]")
    return "\n".join(lines)


def format_status(status: dict) -> str:
    lines = ["Citation workflow status:"]
    for key in ("workflow_id", "query", "candidates", "selected", "matches",
                "attempts", "sources"):
        lines.append(f"  {key}: {status.get(key)}")
    for state in status.get("provider_states", []):
        detail = f" — {state.get('detail')}" if state.get("detail") else ""
        lines.append(f"  provider {state.get('provider')}: {state.get('status')}{detail}")
    return "\n".join(lines)


def _parse_page(args: tuple[str, ...], *, what: str) -> int:
    if not args:
        return 1
    if len(args) > 1 or not args[0].isdigit():
        raise ValueError(f"usage: /citation {what} [page]")
    return int(args[0])


async def run_citation_command(
    coordinator: CitationCoordinator, args: tuple[str, ...]
) -> str:
    """Dispatch one /citation invocation; returns the CLI message."""
    if not args:
        raise ValueError(USAGE)

    head = args[0].lower()
    rest = args[1:]
    if head not in _SUBCOMMANDS:
        # Bare `/citation <query>` is a search.
        return format_search_outcome(await coordinator.search(" ".join(args)))

    if head == "search":
        if not rest:
            raise ValueError("usage: /citation search <query>")
        return format_search_outcome(await coordinator.search(" ".join(rest)))

    if head == "list":
        page = _parse_page(rest, what="list")
        candidates, total_pages = coordinator.list_candidates(page)
        return format_candidates(
            candidates, page=min(page, total_pages), total_pages=total_pages
        )

    if head == "show":
        if len(rest) != 1:
            raise ValueError("usage: /citation show <candidate-id>")
        candidate = coordinator.get_candidate(rest[0])
        if candidate is None:
            return f"unknown or stale candidate id: {rest[0]}"
        return format_candidate_detail(candidate)

    if head == "more":
        query = " ".join(rest) if rest else None
        return format_search_outcome(await coordinator.more(query), appended=True)

    if head == "select":
        if len(rest) != 1:
            raise ValueError("usage: /citation select <candidate-id>")
        outcome: SelectOutcome = await coordinator.select(rest[0])
        if outcome.result is not None:
            return format_result(outcome.result)
        return format_matches(outcome.matches)

    if head == "confirm":
        if len(rest) != 1:
            raise ValueError("usage: /citation confirm <match-id>")
        return format_result(await coordinator.confirm(rest[0]))

    if head == "status":
        if rest:
            raise ValueError("usage: /citation status")
        return format_status(coordinator.status())

    if head == "cancel":
        if rest:
            raise ValueError("usage: /citation cancel")
        return format_result(coordinator.cancel())

    if head == "sources":
        page = _parse_page(rest, what="sources")
        sources, total_pages = coordinator.list_sources(page)
        return format_sources(
            sources, page=min(page, total_pages), total_pages=total_pages
        )

    if head == "source":
        if len(rest) != 1:
            raise ValueError("usage: /citation source <source-id>")
        ref = coordinator.activate_source(rest[0])
        if ref is None:
            return f"unknown source id: {rest[0]}"
        return format_source_detail(ref)

    raise ValueError(USAGE)
