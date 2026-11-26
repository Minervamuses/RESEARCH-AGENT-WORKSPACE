# Change Playbooks

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> Recipes for the recurring kinds of change in this repository, derived from real commits.

## Playbooks

### PLAY-001 — Add or change a desktop protocol v1 method

- **When:** Exposing a new backend capability to the React desktop UI, or adding/renaming fields on an existing RPC request, result, or event.
- **Touch points:**
  1. `app/desktop/protocol/v1/contract.json` — add/update the entry in `methods`, `resultDataSchemas` (or `eventDataSchemas`), and `errorCodes` if needed. Keep payload keys disjoint from `forbiddenDataKeyFragments`.
  2. `app/agent/desktop/protocol.py::validate_result_data` — add any cross-field or conditional rule that declarative `FieldSchema` cannot express (for example `format == "bime_docx"` requiring `audit`). Rust (`app/desktop/src-tauri/src/protocol.rs`) needs edits **only** if `fullTextResultMethods`, `processEvents`, or envelope framing changes.
  3. `app/agent/desktop/<domain>_ops.py` & `app/agent/desktop/service.py::DesktopService.dispatch` — implement the handler on the appropriate mixin (`_ProjectOps`, `_ConversationOps`, `_TurnOps`, `_DocumentOps`, `_BibliographyOps`, `_ExtensionOps`, `_ApprovalOps`), wire it into `dispatch` (noting `project_operation` / `project_read` classification), and map new exceptions in `app/agent/desktop/errors.py::_ErrorMapping._map_exception`.
  4. `app/desktop/src/protocol.ts` — add the TypeScript params/result DTOs and register one entry in `MethodParams` and `MethodResults` (`ProtocolMethod` derives from `keyof MethodResults | MethodWithoutResultDto`).
  5. `app/desktop/src/api.ts::createApi` — expose a typed method (`call(...)` or `tracked(...)` when request-event correlation is needed). `verifyResultEcho` automatically checks `projectId`/`sessionId`/`turnId` declared in both params and result schemas.
  6. `app/desktop/protocol/v1/fixtures.json` — add valid and invalid request/trace fixtures for the method.
- **Keep in sync:** [Sync points](#sync-points) rows 1–3 (`contract.json` <-> `protocol.ts` DTOs, `fixtures.json`, and conditional rules in `protocol.py`).
- **Tests:** `app/tests/test_desktop_protocol_contract.py`, `app/desktop/tests/protocol_types.test.ts`, `app/desktop/tests/api.test.ts`, plus the domain service test (`app/tests/test_desktop_service.py` or `test_desktop_bibliography.py`).
- **Verify:** Focused protocol + `npm test` + `npm run build` ([verification](verification.md#commands)).
- **Pitfalls:**
  - `protocol_types.test.ts` fails `npm test` if any TypeScript DTO property optionality or union type drifts from `contract.json` (`INV-011`).
  - Success results exceeding 2 MiB fail framing unless the method is listed in `fullTextResultMethods` (`ASM-030`).
  - Do not add raw uncalled RPCs "for completeness"; keep declare-and-produce 1:1 (`INV-011`).
- **Worked example:** `dcae226` + `3cc5e26` (`feat(protocol/desktop): bibliography.* methods`), refined by `eda3a44`, `e840c63` (`permissionMode` rename), and `6eef477` (`api.ts`). Note: `dcae226` predated single-source `contract.json` import, so Rust/TS per-method validators touched there are no longer hand-maintained.

### PLAY-002 — Add a desktop UI control or menu action calling the backend

- **When:** Adding a button, dropdown, menu item, or keyboard shortcut in the workspace UI that triggers a backend RPC or native picker.
- **Touch points:**
  1. `app/desktop/src/api.ts` — add or reuse the typed API method (never call `invoke` or `backend.requestTracked` directly from components).
  2. `app/desktop/src/lib/<domain>.ts` — implement pure state/transition/validation helpers (`composer.ts`, `documents.ts`, `approvalOwner.ts`, `extensionFlow.ts`, `interaction.ts`, or `citations.ts`).
  3. `app/desktop/src/App.tsx::App` (or `app/desktop/src/CitationPanel.tsx` for panel-local citation actions) — own the async callback, guard admission (`beginWorkspaceOperation` or `beginDocumentOperation` / `endDocumentOperation`), check `ownsOperation` after every `await`, and pass values + callbacks down as props.
  4. **If the request can emit `approval.required` outside an active turn:** use `tracked(...)` in `api.ts` and bracket the call with `registerApprovalRequest` / `finishApprovalRequest` in `app/desktop/src/lib/approvalOwner.ts` (see `App.tsx::requestCitationAdd`).
  5. `app/desktop/src/components/<Component>.tsx` — render the control using props only (`useDisclosureMenu` for trigger+popup menus; `ModalDialog` for dialogs), setting `disabled` during turns/busy/approval states and `aria-*` attributes.
- **Keep in sync:** [Sync points](#sync-points) rows 4–5 (approval owner registration, keyboard/IME handlers).
- **Tests:** `app/desktop/tests/interaction.test.ts`, `app/desktop/tests/approvalOwner.test.ts`, `app/desktop/tests/conversations.test.ts`, or `app/desktop/tests/citation_preview.test.ts` (asserting roles, labels, and state transitions — never grepping `.tsx` source or class names).
- **Verify:** `cd app/desktop && npm test && npm run build`, plus manual WebKitGTK focus/keyboard check ([verification](verification.md#change-type-matrix)).
- **Pitfalls:**
  - Components under `app/desktop/src/components/` must never import `api` (`INV-015`, `INV-035`).
  - Missing `approvalOwner.ts` registration causes `App.tsx`'s stale-approval effect to immediately dismiss out-of-turn Ask dialogs (`INV-018`).
  - Text inputs that submit on `Enter` must ignore IME composition (`isComposing` / `keyCode === 229`, `INV-022`).
- **Worked example:** `1d3f409` (`feat(desktop): merge the exports into one Export menu with BIME Word`) and `c4d69ee` (`Verify and add`), whose missed out-of-turn Ask approval owner was fixed in `22ae953` (`fix(desktop): keep the bibliography.add approval pending in the GUI`).

### PLAY-003 — Add or refactor a desktop panel, dialog, or stylesheet

- **When:** Introducing a new panel/modal surface, splitting UI presentation, or changing layout/typography rules.
- **Touch points:**
  1. `app/desktop/src/components/Modal.tsx::ModalDialog` or `app/desktop/src/hooks/useDisclosureMenu.ts::useDisclosureMenu` — reuse shared focus-trap, `Escape`, backdrop-dismiss, and blur-close primitives rather than writing ad-hoc key listeners.
  2. `app/desktop/src/components/<Surface>.tsx` — build a stateless/prop-driven component; render any untrusted model/document/citation text through `SafeContent.tsx` or `CitationText.tsx` (`INV-017`).
  3. `app/desktop/src/App.tsx::App` — mount the conditional surface, wire focus restoration (`scheduleOwnedFrame` / `returnFocus`), and set `inert={deleteDialog !== null}` where appropriate.
  4. `app/desktop/src/styles.css` or `app/desktop/src/styles/<section>.css` (`workspace.css`, `sidebar.css`, `conversation.css`, `dialogs.css`, `responsive.css`, `document.css`) — add rules in the matching section stylesheet imported by `app/desktop/src/main.tsx` (no CSS `@import`, no component-level CSS imports).
- **Keep in sync:** [Sync points](#sync-points) row 6 (`styles.test.ts` typography invariants).
- **Tests:** `app/desktop/tests/styles.test.ts`, `app/desktop/tests/interaction.test.ts`, and Node SSR rendering tests in `app/desktop/tests/conversations.test.ts` or `citation_preview.test.ts`.
- **Verify:** `cd app/desktop && npm test && npm run build`, plus native WSLg visual/zoom check (`ASM-025`).
- **Pitfalls:**
  - Preserve `:root` `clamp(1rem, calc(0.75rem + 0.35vw), 1.3125rem)` and `.citation-panel` `>= 0.9rem` (`INV-021`).
  - Inside scrolling containers (`.citation-panel`), flow-positioned menus (`display: contents` + `flex-basis: 100%`) avoid overflow clipping where `position: absolute` would clip.
  - Use `.dialog-error` for dialog validation errors and `.extension-error` only inside `ExtensionPanel.tsx`.
- **Worked example:** `05575ec` (`ModalDialog` + `useDisclosureMenu`), `3760f23` (`Sidebar`, `DocumentPane`, `ProjectChooser` extraction), and `793c5c5` (7-file CSS split).

### PLAY-004 — Add or modify a built-in Skill or agent tool

- **When:** Creating/updating a built-in Skill under `app/skills/<name>/`, adding a base/desktop tool, or changing tool masking (such as read-only document turns).
- **Touch points:**
  1. **For a built-in Skill:** create/edit `app/skills/<name>/SKILL.md` with valid YAML frontmatter (`name`, `description`, optional `tools.required` / `tools.optional`, `references.pinned` validated by `app/agent/skills/manifest_schema.py::validate_skill_manifest`). Keep total pinned + skill text under `AgentConfig.skill_max_total_skill_context_chars` (`200,000`).
  2. **For read-only or mode-forcing Skill behavior:** update `app/agent/session.py::READ_ONLY_DOCUMENT_SKILLS` / `ChatSession.tool_access_resolution` / `ChatSession._locked_turn_outcome`, and update snapshot/reference prompt instructions in `app/agent/desktop/turn_context.py` if desktop document turns behave differently.
  3. **For a local base tool:** add its `BaseToolDoc` and builder in `app/agent/tools/inventory.py` (`BASE_TOOL_DOCS`, `build_base_tools`) so `SYSTEM_PROMPT`, graph binding, and `resolve_tool_access` stay unified.
  4. **For a desktop-injected tool:** construct the `StructuredTool` in `app/agent/desktop/service.py::DesktopService.__init__`, pass it via `extra_tools` in `conversation_ops.py::_ConversationOps._materialize_session`, assign its `mcp_families` bucket in `ChatSession.__init__` (`desktop_document` is ungated at `PolicyToolNode`), and handle split-family availability rendering in `app/agent/skills/runtime.py::render_tool_availability_block`.
  5. **Consent & Stop:** wire `run_local_work` / `current_local_work()` (`app/agent/ingest.py`) for cancellation, and add Ask/Bypass consent in `app/agent/desktop/approvals.py::_ApprovalOps._desktop_operation_approval` if mutating.
- **Keep in sync:** [Sync points](#sync-points) rows 7–8 (`SYSTEM_PROMPT` writing rules, `desktop_document` family split, client/server `@skill` parsing).
- **Tests:** `app/tests/test_skills.py`, `app/tests/test_tool_inventory.py`, `app/tests/test_tool_access_matrix.py`, `app/tests/test_policy_tool_node.py`, `app/tests/test_inline_skills.py`, and skill-specific tests (e.g. `test_grill_skill.py`).
- **Verify:** Focused pytest modules, then full `poetry run pytest` ([verification](verification.md#commands)).
- **Pitfalls:**
  - Never place non-Skill vendor assets under `app/skills/`; `discover_skills` scans every `app/skills/*/SKILL.md` (`INV-019`).
  - Remember `bash` remains globally bound even when `document_edit` is stripped (`ASM-011`); prohibit `bash` file edits explicitly in prompt instructions and verify with `grill_eval.py` when applicable.
- **Worked example:** `d851d94` + `39252be` (`@grill` + `READ_ONLY_DOCUMENT_SKILLS` + split-family `[Tool availability]`) and `81f059b` (`bibliography_lookup` + `_unknown_new_citation_keys`).

### PLAY-005 — Change project metadata, persisted schema, or model-context projection

- **When:** Adding a key to `RESEARCH.md` metadata, changing canonical conversation JSON, or altering how historical/tool document text is projected into LLM prompts.
- **Touch points:**
  1. **`RESEARCH.md` metadata:** update `_PROJECT_METADATA_KEYS` (and `_EDITABLE_METADATA_KEYS` if UI-writable) in `app/agent/desktop/project.py`, keeping `update_project_metadata` byte-preserving outside the JSON block with SHA-256 precheck before `os.replace`.
  2. **Canonical conversation JSON:** update `SCHEMA_VERSION`, key frozensets, dataclasses, and round-trip validators in `app/agent/conversations/models.py` and `app/agent/conversations/repository.py`; update `app/agent/desktop/transcript.py` and `contract.json` if surfaced to UI.
  3. **Model-input document projection:** update shared headers and pure rewrite functions in `app/agent/document_context.py` (`replay_history_inputs`, `compact_edit_results`), wire into `ChatSession._replayed_context` / `graph.py`, and update `app/agent/observability.py::measure_document_context` so `turn_trace` counts stay accurate.
- **Keep in sync:** [Sync points](#sync-points) row 9 (`document_context.py` headers shared by `turn_ops.py`, `document_context.py`, and `observability.py`).
- **Tests:** `app/tests/test_conversation_repository.py`, `app/tests/test_desktop_conversations.py`, `app/tests/test_document_history_replay.py`, `app/tests/test_document_edit_compaction.py`, `app/tests/test_document_measure.py`, `app/tests/test_document_context_budget.py`.
- **Verify:** Focused pytest modules + `scan_cost.py` if conversation file size/parsing changes ([performance](performance.md#how-to-measure)).
- **Pitfalls:**
  - `_parse_metadata` and `_document_from_json` reject unknown keys fail-closed, blocking the entire project from opening (`INV-016`, `FAIL-026`).
  - Never mutate `ConversationTurn` or `state["messages"]` in place when trimming model input (`INV-034`).
- **Worked example:** `f93d6b1` + `1539387` + `0a90b0c` + `5da6a26` (non-destructive history replay, edit-result compaction, and `turn_trace` measurement) and `02f4ff1` (schema v3 enforcement).

### PLAY-006 — Add, update, or remove a runtime or vendored dependency

- **When:** Changing Python packages, Conda toolchain binaries, npm/Cargo packages, or vendored subtrees (`app/vendor/*`). **Requires explicit user approval first (`AGENTS.md`).**
- **Touch points:**
  1. **Python packages:** edit `app/pyproject.toml` and update `app/poetry.lock` inside Conda env `app` (`conda run -n app poetry lock` / `poetry install`; never create `.venv` per `app/poetry.toml`).
  2. **Conda runtime tools:** edit `app/env/env-app.yml` only for non-PyPI binaries (`python`, `poetry`, `nodejs`, `rust`, `pandoc`).
  3. **Desktop frontend / Tauri:** edit `app/desktop/package.json` + `package-lock.json` or `app/desktop/src-tauri/Cargo.toml` + `Cargo.lock` (`main.py::_release_is_current` watches both lockfiles).
  4. **Vendored `bime-word`:** unpack the release zip into an empty temp dir, run `sha256sum -c manifest.sha256`, replace `app/vendor/bime-word/` wholesale without local edits, and re-run `sha256sum -c manifest.sha256` (`README.md`, `INV-029`).
- **Keep in sync:** `README.md` setup instructions and `app/tests/test_extension_packaging.py` (ensuring `app/vendor/*` and `app/scripts/*` stay out of the wheel).
- **Tests:** `app/tests/test_extension_packaging.py`, plus full `pytest`, `npm test`, `npm run build`, and `cargo test --locked`.
- **Verify:** `conda run -n app poetry check` and all four suites ([verification](verification.md#commands)).
- **Pitfalls:**
  - Upgrading `langchain-openrouter` (`==0.2.6`) can break `bounded_sdk_client` client replacement (`ASM-034`).
- **Worked example:** `2442b1d` (vendored `bime-word` + `python-docx`/`lxml`) and `979274d` (`build(deps): remove pybtex now that the BibTeX chain is gone`).

## Sync points

| When you change… | You must also change… | Drift caught by |
|---|---|---|
| `app/desktop/protocol/v1/contract.json` (`methods`, `resultDataSchemas`, `eventDataSchemas`, `submittedContextSchema`, `documentApprovalDataSchema`) | `app/desktop/src/protocol.ts` (`MethodParams`, `MethodResults`, `EventData`, DTO interfaces), `app/desktop/src/api.ts`, and `app/desktop/protocol/v1/fixtures.json` | `app/desktop/tests/protocol_types.test.ts`, `app/tests/test_desktop_protocol_contract.py` |
| `contract.json` framework fields (`protocolVersion`, `maxLineBytes`, `fullTextResultMethods`, `processEvents`, `processEventOrigins`, `forbiddenDataKeyFragments`) | `app/desktop/src-tauri/src/protocol.rs::Framework` and `app/agent/desktop/protocol.py` | `cargo test --locked` (`framework_values_come_from_the_compiled_contract`), `test_desktop_protocol_contract.py` |
| Conditional wire rules in `app/agent/desktop/protocol.py::validate_result_data` (e.g. `bibliography.export` `audit` iff `bime_docx`) | `app/desktop/src/citations.ts` / `protocol.ts` DTOs and `app/desktop/protocol/v1/fixtures.json` traces | `app/tests/test_desktop_protocol_contract.py` (only for cases covered in `fixtures.json`) |
| Requests that can emit `approval.required` in `app/agent/desktop/approvals.py` or `bibliography_ops.py` | Live owner tracking in `app/desktop/src/lib/approvalOwner.ts` + `App.tsx` | `app/desktop/tests/approvalOwner.test.ts` |
| Markdown/LaTeX citekey syntax in `app/skills/citation/citekeys.py` | Editor completion prefix logic in `app/desktop/src/citations.ts::completionPrefix` | `app/tests/test_citation_citekeys_differential.py` (Python vs Pandoc) + `app/desktop/tests/citations.test.ts` (separate; no cross-language test) |
| Inline `@skill` token rules or `composeTurnText` in `app/desktop/src/lib/composer.ts` / `conversations.ts` | `app/agent/skills/runtime.py::resolve_skill_references` and `app/agent/desktop/protocol.py::_validate_skill_references` | `app/tests/test_inline_skills.py` (spawns Node to test TS <-> Python parity) |
| Root font clamp, `.citation-panel` font-size, or Monaco zoom options (`styles.css`, `styles/document.css`, `editorZoom.ts`) | `INV-021` assertions in `app/desktop/tests/styles.test.ts` (`:root` clamp only) and `app/desktop/tests/editorZoom.test.ts` | `app/desktop/tests/styles.test.ts` (`:root` only; `.citation-panel >= 0.9rem` is manual), `app/desktop/tests/editorZoom.test.ts` |
| Embedded document block headers in `app/agent/document_context.py` | Producers in `app/agent/desktop/turn_ops.py` and readers in `app/agent/observability.py::measure_document_context` | Shared constants imported from `document_context.py`; `app/tests/test_document_measure.py` |
| Bundled CSL styles or Appendix 17 rules in `app/skills/citation/styles/styles.json` | `app/skills/citation/csl_render.py::prepare_render_items` | `app/tests/test_citation_csl_render.py`, `app/tests/test_citation_appendix17.py` |
| Desktop stylesheet files under `app/desktop/src/styles/` | Explicit ordered imports in `app/desktop/src/main.tsx` | `nothing` (missing import silently drops rules; verify visually or in `dist/` CSS) |
