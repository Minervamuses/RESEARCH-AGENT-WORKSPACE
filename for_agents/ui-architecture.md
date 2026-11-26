# UI Architecture

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> Surfaces, components, state, controls, styling, and interaction conventions of the user interface.

## Surfaces

| Surface | Component anchor | Shown when | Notes |
|---|---|---|---|
| App shell & skip link | `app/desktop/src/App.tsx::App` | Always | 2-column `.app-shell` grid (`Sidebar` + `#main-workspace`); `inert` while `DeleteConversationDialog` is open |
| Left sidebar | `app/desktop/src/components/Sidebar.tsx::Sidebar` | Always | Brand header, `New conversation`, single `ProjectGroup` (`session-list` + `Load more`), status dot + `Start`/`Restart`/`Shut down` |
| Source document pane | `app/desktop/src/components/DocumentPane.tsx::DocumentPane` | Always (left half of `.writing-workspace`) | `DocumentHeader` (`•••` menu, dirty dot, `Working...`), `DocumentEditor`, conditional `CitationPanel` and `DocumentConflictPanel` |
| Monaco source editor | `app/desktop/src/DocumentEditor.tsx::DocumentEditor` | Inside `DocumentPane` | Shows `.document-editor-empty` until a file opens; dynamically imports local Monaco + worker; portals `AnnotationComment` widgets |
| Citations panel | `app/desktop/src/CitationPanel.tsx::CitationPanel` | `documentValue !== null` and `lifecycle === "ready"` | Starts collapsed per `document.path`; summary bar turns red and auto-expands on initial or `0 -> >0` problems or `Preview`; `ExportMenu` renders in flow |
| Document conflict chooser | `app/desktop/src/components/DocumentPane.tsx::DocumentPane` | `documentConflict !== null` | `DocumentConflictPanel` compares Original, Current editor, Current disk, and Candidate; blocks project switching |
| Lifecycle & empty cards | `app/desktop/src/components/StatusNotices.tsx` | Phase is `starting`, `stopped`, `restarting`, `shutting-down`, `busy`, or `backend-ready` | `PreparingState`, `StoppedState`, `TransitionState`, `LocalRequestState`, `BackendReadyCard` (embeds `RuntimeDetails`) |
| Error & recovery banners | `app/desktop/src/components/StatusNotices.tsx` | Backend/workspace/turn error, Stop failure, or failed refresh | `RecoveryNotice` (4 optional actions), `StopFailureNotice` (`Retry Stop`), `HistoryNotice` (`Refresh without resending`) |
| Extension review card | `app/desktop/src/components/ExtensionPanel.tsx::ExtensionPanel` | `extensionFlow !== null` (after `/extension-management`) | Phases: `ready` -> `previewing` -> `review` (per-binding `Approve`/`Deny` in Ask) -> `applying` -> `applied`/`restarting`/`loaded`/`error` |
| Conversation transcript | `app/desktop/src/components/Transcript.tsx::Transcript` | Active session (`renderConversation`) or `selectionPreview !== null` | `Load older turns`, `.conversation-empty`, `RestoredTurn` (lazy `<details>` tool cards), `CompletedTurn`, `PendingTurn` |
| Passage comment widgets | `app/desktop/src/components/Annotation.tsx::AnnotationComment` | Selection commented in Monaco or transcript | Numbered circular badge + expandable popup; floating `Add comment` (Monaco widget) and fixed `Comment on selection` (`App.tsx`) |
| Composer & menus | `app/desktop/src/components/Composer.tsx::Composer` | Active session (`activeSession !== null` and no preview) | `ComposerNotices`, `ReferenceCards`, comment batch pills, `SlashCommandList` (`/` or `@`), `<textarea>`, `ThinkingControl`, `PermissionControl`, `Send`/`Stop` |
| Project chooser modal | `app/desktop/src/components/ProjectChooser.tsx::ProjectChooser` | Cold start once ready (`chooserOpen` starts `true`), or `Open/Switch project` | `ModalDialog`: `Choose project folder...`, `History directory` + `Inspect`, dirty-document radios, draft-discard checkbox |
| Conversation menu & dialogs | `app/desktop/src/components/ConversationDialogs.tsx` | Right-click on sidebar row (`ConversationMenu`), `Rename`, or `Delete` | Fixed context menu; `RenameConversationDialog` (`<form>`); `DeleteConversationDialog` (stops running turn first) |
| Single-operation approval | `app/desktop/src/components/ApprovalDialog.tsx::ApprovalDialog` | `pendingApproval !== null && deleteDialog === null` | Modal for Bash without open file; non-modal top-right `.document-approval-backdrop` when `allowDocumentEditing` or `approval.operation` is set |

## Component tree

- `app/desktop/src/main.tsx` (mounts `App` and imports the 7 stylesheets in order)
  - `app/desktop/src/App.tsx::App` *(1,928 LOC; owns top-level state, refs, effects, and `api.*` orchestration)*
    - `app/desktop/src/components/Sidebar.tsx::Sidebar` (`ProjectGroup`, `session-list`, backend lifecycle buttons)
    - `main#main-workspace` (`app/desktop/src/components/phaseLabels.ts`)
      - `app/desktop/src/components/DocumentPane.tsx::DocumentPane` (`DocumentHeader`, `DocumentConflictPanel`)
        - `app/desktop/src/DocumentEditor.tsx::DocumentEditor` (Monaco model, `editorZoom.ts`, portal `AnnotationComment`)
        - `app/desktop/src/CitationPanel.tsx::CitationPanel` (`ExportMenu`, `CitedRow`, `UncitedRow`, `app/desktop/src/CitationText.tsx::CitationText`)
      - `div.workspace-body`
        - `app/desktop/src/components/ExtensionPanel.tsx::ExtensionPanel`
        - `app/desktop/src/components/StatusNotices.tsx` (`RecoveryNotice`, `StopFailureNotice`, `HistoryNotice`, empty/transition cards, `BackendReadyCard`)
        - `app/desktop/src/components/Transcript.tsx::Transcript` -> `ConversationTurns` -> `RestoredTurn` | `CompletedTurn` | `PendingTurn`
          - `app/desktop/src/components/messageParts.tsx` (`MessageCard`, `MessageBody`, `ReferenceCards`) & `app/desktop/src/SafeContent.tsx::SafeContent`
          - `app/desktop/src/components/Annotation.tsx::AnnotationComment`
        - `app/desktop/src/components/Composer.tsx` (`ComposerNotices`, `Composer`, `SlashCommandList`, `ComposerFooter`)
          - `app/desktop/src/components/ComposerControls.tsx` (`ThinkingControl`, `PermissionControl`)
        - `app/desktop/src/components/RuntimeDetails.tsx::RuntimeDetails`
    - `app/desktop/src/components/ConversationDialogs.tsx` (`ConversationMenu`, `RenameConversationDialog`, `DeleteConversationDialog`)
    - `app/desktop/src/components/ProjectChooser.tsx::ProjectChooser` (uses `app/desktop/src/components/Modal.tsx::ModalDialog`)
    - `app/desktop/src/components/ApprovalDialog.tsx::ApprovalDialog` (uses `ModalDialog`)

## State ownership

| State | Owner | Source of truth | Persisted | Mutated by |
|---|---|---|---|---|
| Backend phase, snapshot, diagnostics, active `SessionCreatedDto` | `App.tsx` (`useReducer(backendReducer)`) | Rust `BackendSupervisor` + Python `runtime.diagnostics` / `session.*` | No (re-queried per launch/generation) | `dispatch` (`app/desktop/src/backend.ts::backendReducer`) |
| Selected conversation, draft, passage comments, active/submitted turn, Stop state, retry target | `App.tsx` (`conversation` + `conversationRef` via `applyReducerOnce`) | React memory during turn; reconciled with v3 JSON after turn/restart | Drafts/comments: memory only (`resumeDraftRef` across soft restart); turns: v3 JSON | `applyConversation` (`app/desktop/src/conversations.ts::conversationReducer`) |
| Pending approval & live request owners (`turn`, `document`, `citation`) | `App.tsx` (`approval` + `approvalRef`) | Python `approval.required` events + active `TrackedCall.requestId`s | No (60 s TTL, memory only) | `commitApproval` via `app/desktop/src/lib/approvalOwner.ts` |
| Opened project, `sessionList`, paged `transcript`, `liveTurns`, `selectionPreview` | `App.tsx` (`useState` + `projectRef`, `projectEpochRef`) | Python `workspace.select`, `session.list`, `session.transcript` | `RESEARCH.md` & `<historyDirectory>/conversations/*.json` (never auto-reopened on cold start) | `chooseProject`, `loadHistory`, `selectConversation`, `loadOlder`, `sendTurn` |
| Open document buffer, baseline, dirty state, `documentConflict`, Undo target | `App.tsx` (`documentValue`, `documentRef`, `documentBaselineRef`) | Disk on `document.open`/`save`/`apply`; Monaco buffer while editing | Explicit `Save` / approved `document.apply` writes UTF-8 file | `openDocument`, `updateDocument`, `saveDocument`, `applyDocumentOperation`, `resolveDocumentConflict` |
| Editor font size (`10`-`28` px, default `16` px) | `DocumentEditor.tsx` (`editorZoom.ts`) | WebView `localStorage["research-agent.editorFontSize"]` | Yes (`localStorage`, fallback `16` px) | `Ctrl/Cmd` + `=`/`+`/`-`/`0` keybindings in `DocumentEditor.tsx` |
| Citations inspect report, preview segments, export status, expanded toggle | `CitationPanel.tsx` local `useState` (`citationEntries` lifted to `App.tsx`) | Python `bibliography.*` (`references.json` + `RESEARCH.md` `citationStyle`) | `references.json`, `RESEARCH.md`, exported files; `expanded` resets per file | `refresh` (on `refreshToken` / `document.path`), `setStyle`, `renderPreview`, `runExport`, `add`, `remove` |
| Extension preview/apply state machine | `useExtensions` (`app/desktop/src/hooks/useExtensions.ts`) | Python `extensions.preview` / `extensions.apply` + `session.extensionRevision` | Managed copies + registry under `app/tool/` on `Apply` | Pure transitions in `app/desktop/src/lib/extensionFlow.ts` |
| Operation correlation (`generation`, `projectEpoch`, `Symbol`) | `App.tsx` refs (`workspaceOperation`, `documentOperationRef`, `turnOwnerRef`, `exclusiveOwnerRef`) | Rust `snapshot.generation` + local `projectEpochRef` | No | `captureOwner`, `beginWorkspaceOperation`, `beginDocumentOperation`, `invalidateOperations` |

## Controls and actions

| Control | Location | Handler | Effect / backend call | Enabled when | Busy / error behavior |
|---|---|---|---|---|---|
| `Open project` / `Switch project` | `Sidebar.tsx` | `App.tsx::showProjectChooser` | Opens `ProjectChooser` (blocks with `DOCUMENT_CONFLICT` if conflict open) | `idle && lifecycleReady && diagnostics !== null` | Disabled during turns, approvals, or workspace ops |
| `Choose project folder...` / `Open` / `Initialize` | `ProjectChooser.tsx` | `App.tsx::chooseProject` | `api.pickProject` -> `api.workspaceSelect` (`inspect` / `open` / `initialize`) -> `loadHistory` | `!busy`, draft-discard checked if `hasDraft`, history inspected | Shows `<busyLabel>...` and `.dialog-error` inside modal |
| `New conversation` | `Sidebar.tsx` | `App.tsx::createSession` | `window.confirm` if unsent draft -> `api.sessionCreate` | `canCreateSession && !turnActive` | Header shows `Creating conversation`; errors go to `RecoveryNotice` |
| Conversation row / `Load more` / `Load older turns` | `Sidebar.tsx`, `Transcript.tsx` | `selectConversation`, `loadMoreSessions`, `loadOlder` | `selectConversationWithPreview` (`session.transcript` + `session.select`), `api.sessionList`, `api.sessionTranscript` | `!lifecycleBlocked` (`status === "ready"`) | Preview shows `aria-busy="true"`; preserves scroll offset on `Load older` |
| Sidebar right-click `Rename` / `Delete` | `ConversationDialogs.tsx` | `renameConversation`, `deleteConversation` | `api.sessionRename` (`<= 256` B); `Delete` stops active same-session turn (`api.sessionStop`) then `api.sessionDelete` | `Rename`: idle + saved row; `Delete`: idle or targets running conversation | `Saving...` / `Stopping...` / `Deleting...`; errors render in `.dialog-error` |
| `Start` / `Restart` / `Shut down` | `Sidebar.tsx` | `App.tsx::runLifecycle` | `api.start`, `api.restart` (captures `resumeSelection` + `resumeDraft`), `api.shutdown` | `Start`: stopped & idle; `Restart`: running or crashed/degraded (or `stopRecovery`); `Shut down`: idle & running | `TransitionState` spinner; crash/degraded shows `RecoveryNotice` |
| `•••` -> `Open file...` / `Save` (`Ctrl+S`) / `Undo` | `DocumentPane.tsx`, `DocumentEditor.tsx` | `openDocument`, `saveDocument`, `applyDocumentOperation` | `api.pickDocument` -> `api.documentOpen`; `api.documentSave`; `api.documentApplyTracked({undoOfCallId})` | Open: project open & idle; Save: file open & `!documentBusy`; Undo: `lastDocumentAction !== null` & idle | Header shows `Working...`; conflicts open `DocumentConflictPanel`; errors in `.document-error` |
| Editor zoom (`Ctrl/Cmd` + `=`, `-`, `0`) | `DocumentEditor.tsx` | `zoom("in" \| "out" \| "reset")` | Updates Monaco `editorFontOptions` (`lineHeight: 0`) + writes `localStorage` | Editor focused | Clamps to `10`-`28` px; ignores storage errors |
| `Add comment` (`Ctrl/Cmd+Alt+Enter`) / `Comment on selection` | `DocumentEditor.tsx`, `App.tsx` | `addDocumentReference`, `addChatReference` | Captures UTF-16 range + SHA-256 into `conversation.draftReferences` & opens `AnnotationComment` | Active conversation, `idle`, `!chooserOpen`, non-empty selection | Cross-message selection sets `referenceIssue` |
| `Style` / `Preview` / `Export` / `Refresh` | `CitationPanel.tsx` | `setStyle`, `renderPreview`, `runExport`, `refresh` | `bibliography.set_style`, `bibliography.render` (MD only), `bibliography.export` (`docx`, `bime_docx`, `markdown`), `bibliography.inspect` | `Style`/`Export`: `!writesDisabled && working === null` (MD only for Preview/Export) | Shows `Saving style...` / `Formatting...` / `Exporting...` / `Checking...`; errors in `.document-error` |
| `Verify and add` / `Remove` / `Line N` | `CitationPanel.tsx` | `add` (`App.tsx::requestCitationAdd`), `remove`, `jump` | `api.bibliographyAddTracked` (registers `"citation"` approval owner); `window.confirm` -> `api.bibliographyRemove`; selects UTF-16 range | `!writesDisabled` (`Verify and add` requires non-empty input) | `Verifying...`; stale positions prompt `Refresh` |
| Composer `Thinking` / `Permission` | `ComposerControls.tsx` | `updateThinkingMode`, `updatePermissionMode` | `api.sessionSetThinking`, `api.sessionSetPermission` | `!lifecycleBlocked` (frozen during active turn) | Header shows `Updating session controls`; errors go to `RecoveryNotice` |
| Composer `Send` (`Enter`) / `Stop` / `Retry Stop` | `Composer.tsx`, `StopFailureNotice` | `sendTurn`, `stopTurn` | `api.workspaceSelect(inspect)` -> `api.sessionTurnTracked`; `api.sessionStop` | `Send`: non-blank text, `!lifecycleBlocked`, matching retry controls; `Stop`: `!stopping` | `Send` swaps to `Stop` / `Stopping...`; failed Stop shows `StopFailureNotice` |
| `Deny` / `Approve` / `Stop` | `ApprovalDialog.tsx` | `resolvePendingApproval`, `stopTurn` | `api.approvalResolve` (attaches `documentContext` for `document.*` ops); auto-denies at `expiresAt` | `!approvalResolving && stopRequest === null` | Focuses `Deny` on open, restores composer focus on resolve |
| Extension `Preview` / `Approve\|Deny` / `Apply` / `Restart` | `ExtensionPanel.tsx` | `previewExtensions`, `decideBinding`, `applyExtensions`, `restartForExtensions` | `api.extensionsPreview`, `api.extensionsApply`, `runLifecycle("restart")` | `!busy`; `Apply` requires every MCP binding decided under Ask | Phase status text; `.extension-error` with retry/recover buttons |

## Styling system

- **Stylesheet load order (`app/desktop/src/main.tsx`):** Seven plain CSS files imported in fixed order with zero CSS `@import` and zero component CSS imports:
  1. `app/desktop/src/styles.css` - `:root` typography/colors, reset, buttons, `.skip-link`, `.app-shell`, `.sidebar` frame, `.status-dot`, `.control-row`.
  2. `app/desktop/src/styles/workspace.css` - `.main-workspace`, `.workspace-header`, `.workspace-body`, `.empty-state`, `.primary-button`, `.notice`, `.setup-card`, `.runtime-details`, `.spinner`, `.session-meta`.
  3. `app/desktop/src/styles/sidebar.css` - `.project-browser`, `.project-group`, `.session-list`, `.session-link`, `.conversation-menu`.
  4. `app/desktop/src/styles/conversation.css` - `.conversation-workspace-body`, `.transcript`, `.turn-group`, `.message` variants, `.tool-activity`, `.safe-content`, `.composer`, `.slash-command-list`, `.thinking-*`, `.bash-permission-control`.
  5. `app/desktop/src/styles/dialogs.css` - `.extension-card`, `.approval-context`, `.extension-error` / `.dialog-error` / `.error-text` (`#843c38 !important`), `.modal-backdrop`, `.modal-dialog`.
  6. `app/desktop/src/styles/responsive.css` - `@media (max-width: 760px)` and `@media (max-width: 520px)` shell/sidebar/card collapses.
  7. `app/desktop/src/styles/document.css` - `.writing-workspace` (`1.05fr` / `1fr` split, 1 column at `@media (max-width: 1050px)`), `.document-pane`, `.document-conflict`, `.document-approval-backdrop`, `.reference-cards`, `.annotation-*`, `.citation-panel`.
- **Typography & zoom (`INV-021`, `app/desktop/tests/styles.test.ts`):** Root `font-size: clamp(1rem, calc(0.75rem + 0.35vw), 1.3125rem)`; `.citation-panel` is `0.95rem` (notes `0.9rem`, never `< 0.9rem`); Monaco uses `16px` default (`10`-`28px`, `lineHeight: 0` in `app/desktop/src/editorZoom.ts`).
- **Palette & window:** Light-only warm neutral palette (`#f7f7f5` shell, `#eeeeeb` sidebar, `#236c55` primary accent, `#843c38` error; 110 hex and 16 `rgba` literals, no CSS custom-property tokens). Window defaults to `1080x720`, min `720x560` (`app/desktop/src-tauri/tauri.conf.json`).

## Interaction conventions

- **Dialogs (`app/desktop/src/components/Modal.tsx::ModalDialog`, `lib/interaction.ts::dialogKeyDecision`):** Shared backdrop + `role="dialog"`. `modal={true}` traps `Tab`/`Shift+Tab` inside `focusSelector`; `Escape` dismisses when `dismissible` (`!busy`). `ApprovalDialog` focuses `Deny` first and switches to non-modal (`modal={false}`, `pointer-events: none` backdrop) when a document is open or `approval.operation` is set so the editor stays reachable; `Escape` still denies, while backdrop clicks do not.
- **Menus (`app/desktop/src/hooks/useDisclosureMenu.ts`, `DocumentPane.tsx`, `ConversationDialogs.tsx`):** `ThinkingControl` and `ExportMenu` share `useDisclosureMenu` (close on disable or outside blur, focus initial item on open, close + focus trigger on `Escape`). `DocumentHeader` `<details>` mirrors blur/Escape close; `ConversationMenu` clamps `(left, top)` to the viewport and restores row focus on `onClose`.
- **Confirmations:** `Delete conversation` uses `DeleteConversationDialog` (`ModalDialog` with `inert` background); discarding unsaved edits/drafts and `CitationPanel` `Remove` use `window.confirm` (`citations.ts::removeConfirmation` warns sibling files are unchecked).
- **Keyboard & IME (`INV-022`, `app/desktop/src/lib/composer.ts`):** `Shift+Enter` adds a newline; IME composition (`isComposing`, plus `keyCode === 229` in `Annotation.tsx` and `RenameConversationDialog`) never submits; open `/` or `@` menus trap `ArrowUp`/`ArrowDown`/`Enter`/`Escape`; plain `Enter` submits `Composer` and collapses `AnnotationComment`.
- **Safe content & links (`INV-017`):** `SafeContent.tsx` and `CitationText.tsx` build React element arrays (never `dangerouslySetInnerHTML`) and gate links through `safeExternalUrl` (`http:`/`https:` without credentials).

## UI constraints and debt

- **Coordinator size in `App.tsx`:** Presentation lives in `src/components/*` and pure helpers in `src/lib/*`, but `app/desktop/src/App.tsx` (1,928 LOC) retains 33 `useState`, 33 `useRef`, 11 `useEffect`, and 46 `useCallback` hooks due to coupled approval/snapshot effect ordering.
- **CSS & IME gaps:** Raw color literals have no CSS custom-property tokens yet; `.approval-context`, `.file-open-dialog`, and `.bash-permission-control` keep historical class names; `.annotation-comment` uses fixed `13px` (`INV-021`); `Composer.tsx` omits the `keyCode === 229` IME fallback (`INV-022`).
- **WSLg WebKitGTK & SSR boundary (`ASM-025`):** WSLg D3D12 requires `GALLIUM_DRIVER=d3d12` + `WEBKIT_DISABLE_DMABUF_RENDERER=1` (`main.py::_desktop_environment`). `npm test` uses Node SSR without a live browser layout engine or Monaco worker ([verification](verification.md#coverage-gaps)).
