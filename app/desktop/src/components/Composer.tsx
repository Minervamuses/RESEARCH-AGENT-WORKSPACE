import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import type { PermissionMode, Reference } from "../protocol.ts";
import {
  filterSlashCommands,
  handleComposerKey,
  inlineSkillToken,
  insertInlineSkill,
  insertSlashCommand,
  slashPrefix,
  type SlashCommands,
} from "../lib/composer.ts";
import type { AnnotationControls } from "./Annotation.tsx";
import { PermissionControl, ThinkingControl } from "./ComposerControls.tsx";
import { ReferenceCards } from "./messageParts.tsx";

export function SlashCommandList({ commands, active, onSelect, inline = false }: {
  commands: SlashCommands; active: number; onSelect: (index: number) => void; inline?: boolean;
}) {
  return <ul id="composer-slash-commands" className="slash-command-list" role="listbox" aria-label={inline ? "Skills" : "Slash commands"}>
    {commands.map((command, index) => <li
      key={command.name} id={`composer-slash-option-${index}`} role="option"
      aria-selected={index === active}
      onPointerDown={(event) => event.preventDefault()}
      onClick={() => onSelect(index)}
    ><strong>{inline ? "@" : "/"}{command.name}</strong><span>{command.description}</span></li>)}
  </ul>;
}

export function ComposerFooter({ thinkingMode, permissionMode, controlsDisabled, sendDisabled, turnActive = false, stopping = false, onStop, onThinkingChange, onPermissionChange }: {
  thinkingMode: "normal" | "extended"; permissionMode: PermissionMode;
  controlsDisabled: boolean; sendDisabled: boolean;
  turnActive?: boolean; stopping?: boolean; onStop?: () => void;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: PermissionMode) => void;
}) {
  return <div className="composer-footer">
    <div className="composer-controls" aria-label="Conversation settings">
      <ThinkingControl mode={thinkingMode} disabled={controlsDisabled} onChange={onThinkingChange} />
      <PermissionControl mode={permissionMode} disabled={controlsDisabled} onChange={onPermissionChange} />
    </div>
    {turnActive
      ? <button className="primary-button" type="button" disabled={stopping} onClick={onStop}>{stopping ? "Stopping…" : "Stop"}</button>
      : <button className="primary-button" type="submit" disabled={sendDisabled}>Send</button>}
  </div>;
}

export function Composer({ draft, references, annotationControls, onRemoveReference, commands, skills, onSkillPicked, textareaRef, disabled, sendDisabled, controlsDisabled, turnActive, stopping, onStop, thinkingMode, permissionMode, onThinkingChange, onPermissionChange, turnHint, onChange, onSubmit }: {
  references: readonly Reference[]; onRemoveReference: (id: string) => void;
  annotationControls: AnnotationControls;
  turnActive: boolean; stopping: boolean; onStop: () => void;
  thinkingMode: "normal" | "extended"; permissionMode: PermissionMode; controlsDisabled: boolean; turnHint?: string;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: PermissionMode) => void;
  draft: string; commands: SlashCommands; skills: readonly string[]; onSkillPicked: (name: string) => void; textareaRef: RefObject<HTMLTextAreaElement | null>;
  disabled: boolean; sendDisabled: boolean; onChange: (draft: string) => void; onSubmit: () => void;
}) {
  const [focused, setFocused] = useState(false);
  const [cursor, setCursor] = useState({ start: 0, end: 0 });
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [composing, setComposing] = useState(false);
  const composingRef = useRef(false);
  const insertion = useRef<{ text: string; caret: number } | null>(null);
  const [selection, setSelection] = useState({ draft, commands, index: 0 });
  const prefix = slashPrefix(draft, cursor.start, cursor.end);
  const inline = inlineSkillToken(draft, cursor.start, cursor.end);
  const inlinePrefix = inline?.prefix ?? null;
  const matches = useMemo(() => inlinePrefix === null
    ? filterSlashCommands(commands, prefix ?? "")
    : skills.filter((name) => name.toLowerCase().startsWith(inlinePrefix.toLowerCase()))
      .map((name) => ({ name, description: commands.find((item) => item.name === name)?.description ?? "Use this Skill for the current message" })),
    [commands, skills, prefix, inlinePrefix]);
  const open = focused && !disabled && !composing && (inline !== null || commands.length > 0) &&
    dismissed !== draft && (inline !== null || prefix !== null);
  const active = selection.draft === draft && selection.commands === commands
    ? Math.min(selection.index, Math.max(0, matches.length - 1)) : 0;

  useLayoutEffect(() => {
    if (insertion.current?.text !== draft) return;
    const caret = insertion.current.caret;
    insertion.current = null;
    textareaRef.current?.focus();
    textareaRef.current?.setSelectionRange(caret, caret);
    setCursor({ start: caret, end: caret });
  }, [draft, textareaRef]);

  useEffect(() => {
    if (open) document.getElementById(`composer-slash-option-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, open, matches]);

  const select = (index: number) => {
    if (!open || composingRef.current || matches[index] === undefined) return;
    const inserted = inline === null
      ? { text: insertSlashCommand(draft, matches[index].name), caret: insertSlashCommand(draft, matches[index].name).length }
      : insertInlineSkill(draft, inline, matches[index].name);
    if (inline !== null) onSkillPicked(matches[index].name);
    insertion.current = inserted;
    setDismissed(inserted.text);
    onChange(inserted.text);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    handleComposerKey({
      key: event.key, shiftKey: event.shiftKey,
      isComposing: event.nativeEvent.isComposing || composingRef.current,
      preventDefault: () => event.preventDefault(),
    }, { open, count: matches.length, active }, {
      select,
      move: (index) => setSelection({ draft, commands, index }),
      close: () => setDismissed(draft),
      submit: onSubmit,
    });
  };

  return <form className="composer" onSubmit={(event) => {
    event.preventDefault();
    if (!composingRef.current) onSubmit();
  }}>
    <label htmlFor="conversation-draft">Message</label>
    <ReferenceCards references={references.filter((reference) => !annotationControls.annotations.some((item) => item.referenceId === reference.referenceId))}
      onRemove={disabled ? undefined : onRemoveReference} />
    {annotationControls.annotations.length > 0 && <div className="annotation-batch" data-reference-exclude>
      <span>{annotationControls.annotations.length} passage comments</span>
      {annotationControls.annotations.map((annotation) => <button key={annotation.referenceId} type="button" disabled={disabled}
        title={annotation.comment || "No request yet"} onClick={() => annotationControls.onToggle(annotation.referenceId, true)}>
        {annotation.number}{annotation.comment.trim() === "" ? " · empty" : ""}
      </button>)}
      {draft.trim() === "" && annotationControls.annotations.every((item) => item.comment.trim() === "") &&
        <span>Add a comment or a message before sending.</span>}
    </div>}
    {open && <>
      <SlashCommandList commands={matches} active={active} onSelect={select} inline={inline !== null} />
      <span className="slash-command-status" role="status">{matches.length === 0 ? (inline !== null ? "No matching Skill. Unselected @ text is sent literally." : "No matching commands") : `${matches.length} ${inline !== null ? "Skills" : "commands"} · ↑↓ to move · Enter to insert · Esc to close`}</span>
    </>}
    <textarea id="conversation-draft" ref={textareaRef} value={draft}
      onChange={(event) => {
        setDismissed(null);
        setCursor({ start: event.target.selectionStart, end: event.target.selectionEnd });
        onChange(event.target.value);
      }}
      onSelect={(event) => setCursor({ start: event.currentTarget.selectionStart, end: event.currentTarget.selectionEnd })}
      onFocus={(event) => {
        setFocused(true);
        setCursor({ start: event.target.selectionStart, end: event.target.selectionEnd });
      }}
      onBlur={() => setFocused(false)}
      onCompositionStart={() => { composingRef.current = true; setComposing(true); }}
      onCompositionEnd={() => { composingRef.current = false; setComposing(false); }}
      onKeyDown={onKeyDown}
      aria-autocomplete="list" aria-haspopup="listbox"
      aria-controls={open ? "composer-slash-commands" : undefined}
      aria-activedescendant={open && matches.length > 0 ? `composer-slash-option-${active}` : undefined}
      rows={3} title="Enter to send · Shift+Enter for a new line · @ to add a Skill" placeholder="Ask about your research…" disabled={disabled}
    />
    {turnHint !== undefined && <p className="composer-turn-hint" role="status">{turnHint}</p>}
    <ComposerFooter thinkingMode={thinkingMode} permissionMode={permissionMode} controlsDisabled={controlsDisabled}
      sendDisabled={sendDisabled} turnActive={turnActive} stopping={stopping} onStop={onStop}
      onThinkingChange={onThinkingChange} onPermissionChange={onPermissionChange} />
  </form>;
}
