import { sameSelection, type ConversationSelection } from "../conversations.ts";
import type { PermissionMode, SessionCreatedDto, SubmittedContext } from "../protocol.ts";

export type SlashCommands = SessionCreatedDto["slashCommands"];

export type SlashCatalogOwner = ConversationSelection & { generation: number };

export const NO_SLASH_COMMANDS: SlashCommands = [];

export function shouldSubmitComposerKey(
  key: string,
  shiftKey: boolean,
  isComposing: boolean,
): boolean {
  return key === "Enter" && !shiftKey && !isComposing;
}

export function composerSlashCommands(
  session: SessionCreatedDto | null,
  selected: ConversationSelection | null,
  generation: number | undefined,
  owner: SlashCatalogOwner | null,
  interactive: boolean,
): SlashCommands {
  if (!interactive || owner === null || selected === null || owner.generation !== generation ||
      !sameSelection(owner, selected) || session?.sessionId !== owner.sessionId ||
      (session.projectId !== undefined && session.projectId !== owner.projectId)) {
    return NO_SLASH_COMMANDS;
  }
  return session.slashCommands;
}

export function slashPrefix(draft: string, start: number, end: number): string | null {
  if (start !== end || end !== draft.length) return null;
  return /^[^\S\r\n]*\/([^\s/]*)$/.exec(draft)?.[1] ?? null;
}

export function filterSlashCommands(commands: SlashCommands, prefix: string): SlashCommands {
  return commands.filter((command) => command.name.toLowerCase().startsWith(prefix.toLowerCase()));
}

export function insertSlashCommand(draft: string, name: string): string {
  return `${/^[^\S\r\n]*/.exec(draft)?.[0] ?? ""}/${name} `;
}

export interface InlineSkillReference { name: string; startUtf16: number; endUtf16: number }

export function inlineSkillToken(draft: string, start: number, end: number): { start: number; end: number; prefix: string } | null {
  if (start !== end) return null;
  let tokenStart = start;
  while (tokenStart > 0 && /[A-Za-z0-9_-]/.test(draft[tokenStart - 1])) tokenStart -= 1;
  if (tokenStart === 0 || draft[tokenStart - 1] !== "@") return null;
  const at = tokenStart - 1;
  if (at > 0 && /[A-Za-z0-9_.@+-]/.test(draft[at - 1])) return null;
  let tokenEnd = start;
  while (tokenEnd < draft.length && /[A-Za-z0-9_-]/.test(draft[tokenEnd])) tokenEnd += 1;
  if (draft[tokenEnd] === "." && /[A-Za-z0-9]/.test(draft[tokenEnd + 1] ?? "")) return null;
  return { start: at, end: tokenEnd, prefix: draft.slice(tokenStart, start) };
}

export function insertInlineSkill(draft: string, token: { start: number; end: number }, name: string): { text: string; caret: number } {
  const replacement = "@" + name + (token.end === draft.length ? " " : "");
  return { text: draft.slice(0, token.start) + replacement + draft.slice(token.end), caret: token.start + replacement.length };
}

export function inlineSkillReferences(draft: string, skills: readonly string[], selectedNames: ReadonlySet<string> = new Set()): InlineSkillReference[] {
  const available = new Set(skills);
  const references: InlineSkillReference[] = [];
  for (const match of draft.matchAll(/@([A-Za-z0-9][A-Za-z0-9_-]*)/g)) {
    const start = match.index!;
    const end = start + match[0].length;
    const token = inlineSkillToken(draft, end, end);
    if (token === null || token.start !== start) continue;
    if (!available.has(match[1])) {
      if (selectedNames.has(match[1])) throw new Error("Selected Skill is no longer available: " + match[1]);
      continue;
    }
    references.push({ name: match[1], startUtf16: start, endUtf16: end });
  }
  return references;
}

export function handleComposerKey(
  event: { key: string; shiftKey: boolean; isComposing: boolean; preventDefault: () => void },
  menu: { open: boolean; count: number; active: number },
  actions: { select: (index: number) => void; move: (index: number) => void; close: () => void; submit: () => void },
): void {
  if (event.isComposing) return;
  if (menu.open) {
    if (event.key === "Escape") {
      event.preventDefault();
      actions.close();
      return;
    }
    if (menu.count > 0) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        actions.move((menu.active + (event.key === "ArrowDown" ? 1 : menu.count - 1)) % menu.count);
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        actions.select(menu.active);
        return;
      }
    }
  }
  if (shouldSubmitComposerKey(event.key, event.shiftKey, event.isComposing)) {
    event.preventDefault();
    actions.submit();
  }
}

export function checkSubmissionSize(text: string, submittedContext: SubmittedContext | null): void {
  const input = submittedContext === null ? text : JSON.stringify({ text, submittedContext });
  if (new TextEncoder().encode(input).byteLength > 1024 * 1024) {
    throw new Error("This submission exceeds the 1 MiB input limit. Remove references or use a smaller source document; your draft is retained.");
  }
}

export function retrySettingsMatch(context: SubmittedContext | null, permission: PermissionMode, thinking: "normal" | "extended"): boolean {
  return context === null || (context.permissionMode === permission && context.requestedThinkingMode === thinking);
}

export function handleAnnotationKey(event: {
  key: string; shiftKey: boolean; isComposing: boolean;
  preventDefault: () => void; stopPropagation: () => void;
}, confirm: () => void): void {
  event.stopPropagation();
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  confirm();
}
