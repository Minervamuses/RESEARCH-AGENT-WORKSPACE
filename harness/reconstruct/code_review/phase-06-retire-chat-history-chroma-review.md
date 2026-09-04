# Phase 06 Review — Retire Conversation-History Chroma

## Scope

Fresh read-only review of Phase 06 through application/tests commit `474a9b5`, active-docs commit `001b15a`, Green evidence `7fcd2fd`, and review-fix commit `75fa8a2`. The review checked the live runtime boundary, canonical archive access, legacy migration isolation, fixed latest-10 context, document RAG preservation, and active documentation.

## Resolved findings

1. Desktop imported the migration stack eagerly. Migration construction is now lazy and occurs only after a canonical miss; normal fixture startup proves the legacy/Chroma modules are not loaded.
2. Prompt-first persistence makes the current lookup query match its own pending record. Archive recovery now accepts only earlier completed turns and never treats the current pending match as history.
3. Raw text and JSON-content escaping were insufficient as shell syntax. Guidance now requires POSIX single-argument quoting for both phrase and root, retains `--`, and specifies the exact `grep -lF ... | head -n 21` shape. Metacharacter, quote, backslash, and newline fixtures pass through the approved real grep runner without expansion.
4. Archive fan-out and large-file reads needed explicit bounds. A 21st candidate causes zero file reads and a narrowing request; canonical UUID JSON files can be read with UTF-8-safe cursors up to the schema's 8 MiB bound, while arbitrary files retain the 1 MiB rejection.
5. An implementation draft made the latest-context window configurable despite stable `JSON-INV-006`. The config was removed; normal session and Desktop fixture derive exactly the latest ten eligible completed turns from `ConversationRepository`.
6. The real Desktop fixture omitted `conversation_root` from `/status`, causing a `KeyError`. It now uses the same validated repository display root and has a focused service-level regression test.
7. Active docs still described provider failures as unrecorded and catalog registration as post-final. They now describe durable failed turns and registration after the first durable pending prompt.

## Final result

- No open P1/P2 finding.
- Normal agent/Desktop runtime has no conversation-history Chroma construction, query, write, eviction, or flush path, and exposes no `recall_history` tool.
- Legacy Chroma remains a non-destructive, migration-only reader; document RAG and its Chroma/Ollama dependencies remain intact.
- Archive access remains user-approved, exact-text-only, bounded, shell-quoted, and separate from document RAG.

## Evidence

- Phase-required Python selector after final fixes: `184 passed, 1` existing LangGraph warning.
- Archive/history/Desktop fixture selector after final fixes: `28 passed, 1` existing LangGraph warning.
- Wider affected selector before the last localized review fix: `610 passed, 1` existing LangGraph warning.
- Exact residue search, `manage_for_agents.py check`, and `git diff --check`: passed with only the recorded allowlisted warnings/references.
