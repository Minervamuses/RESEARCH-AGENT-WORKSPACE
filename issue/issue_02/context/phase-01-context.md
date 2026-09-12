# Phase 01 — Catalog bounds

2026-09-12 observed implementation decision:

- Required `slashCommands` is an ordered object array, at most 512 entries.
- Canonical `name` is unchanged, at most 64 UTF-8 bytes (existing dynamic registry limit).
- `description` is bounded with the existing UTF-8 helper to 1024 bytes.
- Producer raises PROTOCOL_INVALID if count/name exceeds bounds; it never slices the
  command list or changes command identity. Tests distinguish 512 from 513 entries.
- Catalog contents therefore stay well below the existing 2 MiB envelope for ordinary
  text. Existing envelope enforcement still applies to the entire serialized snapshot
  including diagnostics and JSON escaping; no new paging or silent partial result.
- All three validators require the field. There is no mixed-version compatibility claim.
