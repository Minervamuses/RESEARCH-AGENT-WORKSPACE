import { createElement, type ReactNode } from "react";
import { openSafeExternalUrl, safeExternalUrl, type ExternalUrlOpener } from "./lib/safeUrl.ts";
import { openUrl } from "@tauri-apps/plugin-opener";
import type { RenderSegmentDto } from "./citations.ts";

/**
 * Formatted reference text from bibliography.render. Segments carry italics,
 * bold and links as data, so nothing is parsed as Markup or HTML; links use
 * the same http(s)-only check as SafeContent at click time.
 */
export function CitationText({ segments, openExternal = openUrl }: { segments: readonly RenderSegmentDto[]; openExternal?: ExternalUrlOpener }) {
  const children: ReactNode[] = segments.map((segment, index) => {
    let node: ReactNode = segment.text;
    if (segment.url !== null && safeExternalUrl(segment.url) !== null) {
      const url = segment.url;
      node = createElement("button", {
        key: `l${index}`, type: "button", className: "safe-link",
        onClick: () => { void openSafeExternalUrl(url, openExternal); },
      }, node);
    }
    if (segment.bold) node = createElement("strong", { key: `b${index}` }, node);
    if (segment.italic) node = createElement("em", { key: `i${index}` }, node);
    return typeof node === "string" ? createElement("span", { key: `t${index}` }, node) : node;
  });
  return createElement("span", { className: "citation-text" }, children);
}
