export type ExternalUrlOpener = (url: string) => void | Promise<void>;

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
