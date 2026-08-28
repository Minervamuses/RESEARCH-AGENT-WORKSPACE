import { openUrl } from "@tauri-apps/plugin-opener";
import { Fragment, createElement, type ReactNode } from "react";

export type ExternalUrlOpener = (url: string) => void | Promise<void>;

export interface SafeContentProps {
  content: string;
  openExternal?: ExternalUrlOpener;
}

interface TextToken {
  kind: "text" | "code" | "strong" | "emphasis" | "link";
  text: string;
  url?: string;
}

function defaultOpenExternal(url: string): Promise<void> {
  return openUrl(url);
}

/**
 * Returns a canonical external URL only when it is safe to hand to the native
 * opener. This must also run at click time, because rendered content is not a
 * trusted authority for a URL.
 */
export function safeExternalUrl(value: string): string | null {
  if (value !== value.trim()) return null;

  try {
    const parsed = new URL(value);
    if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || !parsed.hostname) {
      return null;
    }
    if (parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export async function openSafeExternalUrl(
  value: string,
  openExternal: ExternalUrlOpener,
): Promise<boolean> {
  const safeUrl = safeExternalUrl(value);
  if (safeUrl === null) return false;
  await openExternal(safeUrl);
  return true;
}

function findClosing(value: string, marker: string, from: number): number {
  const index = value.indexOf(marker, from);
  return index;
}

function parseInline(value: string): TextToken[] {
  const tokens: TextToken[] = [];
  let text = "";
  let index = 0;
  const appendText = (part: string) => {
    text += part;
  };
  const flushText = () => {
    if (text) tokens.push({ kind: "text", text });
    text = "";
  };

  while (index < value.length) {
    if (value[index] === "`") {
      const end = findClosing(value, "`", index + 1);
      if (end !== -1) {
        flushText();
        tokens.push({ kind: "code", text: value.slice(index + 1, end) });
        index = end + 1;
        continue;
      }
    }

    if (value[index] === "[" && value[index - 1] !== "!") {
      const labelEnd = value.indexOf("](", index + 1);
      if (labelEnd !== -1) {
        const urlEnd = value.indexOf(")", labelEnd + 2);
        if (urlEnd !== -1) {
          flushText();
          tokens.push({
            kind: "link",
            text: value.slice(index + 1, labelEnd),
            url: value.slice(labelEnd + 2, urlEnd),
          });
          index = urlEnd + 1;
          continue;
        }
      }
    }

    const marker = value.startsWith("**", index) || value.startsWith("__", index)
      ? value.slice(index, index + 2)
      : value[index] === "*" || value[index] === "_"
        ? value[index]
        : null;
    if (marker) {
      const end = findClosing(value, marker, index + marker.length);
      if (end !== -1 && end > index + marker.length) {
        flushText();
        tokens.push({
          kind: marker.length === 2 ? "strong" : "emphasis",
          text: value.slice(index + marker.length, end),
        });
        index = end + marker.length;
        continue;
      }
    }

    appendText(value[index]);
    index += 1;
  }
  flushText();
  return tokens;
}

function InlineContent({ value, openExternal }: { value: string; openExternal: ExternalUrlOpener }) {
  const children: ReactNode[] = [];
  for (const [index, token] of parseInline(value).entries()) {
    const key = `${token.kind}-${index}`;
    if (token.kind === "code") {
      children.push(createElement("code", { key }, token.text));
    } else if (token.kind === "strong") {
      children.push(createElement("strong", { key }, token.text));
    } else if (token.kind === "emphasis") {
      children.push(createElement("em", { key }, token.text));
    } else if (token.kind === "link") {
      const safeUrl = token.url === undefined ? null : safeExternalUrl(token.url);
      if (safeUrl === null) {
        children.push(createElement("span", { key }, token.text));
      } else {
        children.push(
          createElement(
            "button",
            {
              key,
              type: "button",
              className: "safe-link",
              onClick: () => {
                void openSafeExternalUrl(token.url ?? "", openExternal);
              },
            },
            token.text,
          ),
        );
      }
    } else {
      children.push(token.text);
    }
  }
  return createElement(Fragment, null, ...children);
}

function paragraph(lines: string[], key: string, openExternal: ExternalUrlOpener): ReactNode {
  return createElement(
    "p",
    { key },
    createElement(InlineContent, { value: lines.join(" "), openExternal }),
  );
}

/**
 * A deliberately small Markdown renderer for agent output. It builds React
 * elements directly, so HTML from the model is always displayed as text.
 */
export function SafeContent({ content, openExternal = defaultOpenExternal }: SafeContentProps) {
  const blocks: ReactNode[] = [];
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (line.trim() === "") {
      index += 1;
      continue;
    }

    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push(createElement("pre", { key: `code-${index}` }, createElement("code", null, codeLines.join("\n"))));
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      blocks.push(
        createElement(
          `h${level}`,
          { key: `heading-${index}` },
          createElement(InlineContent, { value: heading[2], openExternal }),
        ),
      );
      index += 1;
      continue;
    }

    const unordered = /^[-*]\s+(.+)$/.exec(line);
    const ordered = /^\d+[.)]\s+(.+)$/.exec(line);
    if (unordered || ordered) {
      const isOrdered = Boolean(ordered);
      const items: ReactNode[] = [];
      const matcher = isOrdered ? /^\d+[.)]\s+(.+)$/ : /^[-*]\s+(.+)$/;
      while (index < lines.length) {
        const item = matcher.exec(lines[index]);
        if (!item) break;
        items.push(
          createElement(
            "li",
            { key: `item-${index}` },
            createElement(InlineContent, { value: item[1], openExternal }),
          ),
        );
        index += 1;
      }
      blocks.push(createElement(isOrdered ? "ol" : "ul", { key: `list-${index}` }, ...items));
      continue;
    }

    const paragraphLines = [line];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() !== "" &&
      !lines[index].startsWith("```") &&
      !/^(#{1,3})\s+/.test(lines[index]) &&
      !/^[-*]\s+/.test(lines[index]) &&
      !/^\d+[.)]\s+/.test(lines[index])
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push(paragraph(paragraphLines, `paragraph-${index}`, openExternal));
  }

  return createElement("div", { className: "safe-content" }, ...blocks);
}
