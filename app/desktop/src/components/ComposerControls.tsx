import type { PermissionMode } from "../protocol.ts";
import { useDisclosureMenu } from "../hooks/useDisclosureMenu.ts";
import { menuNextIndex } from "../lib/interaction.ts";

export interface PermissionControlProps {
  mode: PermissionMode;
  disabled: boolean;
  onChange: (mode: PermissionMode) => void;
}

export function PermissionControl({
  mode,
  disabled,
  onChange,
}: PermissionControlProps) {
  return (
    <label className="bash-permission-control">
      Permission
      <select
        aria-label="Permission"
        title={disabled ? "The current turn keeps its starting mode. Change the mode after it finishes." : "Applies to document edits, Bash, citation saves, indexing, MCP and extensions."}
        value={mode}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as PermissionMode)}
      >
        <option value="ask">Ask</option>
        <option value="bypass">Bypass</option>
      </select>
    </label>
  );
}

export function ThinkingControl({ mode, disabled, onChange }: {
  mode: "normal" | "extended"; disabled: boolean; onChange: (mode: "normal" | "extended") => void;
}) {
  const { open, setOpen, close, triggerRef, menuRef, containerProps } = useDisclosureMenu<HTMLDivElement>(disabled, '[aria-checked="true"]');
  const label = mode === "normal" ? "Normal" : "Extended";
  return <div className="thinking-control" {...containerProps}>
    <button ref={triggerRef} className="thinking-trigger" type="button" disabled={disabled}
      aria-label={"Thinking: " + label} aria-haspopup="menu" aria-expanded={open}
      title={"Thinking: " + label + (disabled ? ". The current turn keeps its starting mode." : ". Document and citation tasks use Normal when required.")}
      onClick={() => setOpen(!open)}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" && !disabled) { event.preventDefault(); setOpen(true); }
      }}>
      <svg aria-hidden="true" viewBox="0 0 20 20" width="18" height="18"><path d="m10 2 2.1 5.9L18 10l-5.9 2.1L10 18l-2.1-5.9L2 10l5.9-2.1Z" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      <span>{label}</span>
    </button>
    <div ref={menuRef} className="thinking-options" role="menu" aria-label="Thinking mode" hidden={!open}
      onKeyDown={(event) => {
        const options = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
        const next = menuNextIndex(event.key, options.indexOf(document.activeElement as HTMLButtonElement), options.length, true);
        if (next === null) return;
        event.preventDefault();
        options[next]?.focus();
      }}>
      {(["normal", "extended"] as const).map((value) => <button type="button" role="menuitemradio"
        aria-checked={mode === value} tabIndex={mode === value ? 0 : -1} disabled={disabled} key={value}
        onClick={() => { close(); onChange(value); }}>{value === "normal" ? "Normal" : "Extended"}</button>)}
    </div>
  </div>;
}
