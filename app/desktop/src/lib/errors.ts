import {
  BackendClientError,
  type SafeUiError,
  normalizeUiError,
} from "../backend.ts";

export function workspaceError(error: unknown): SafeUiError {
  return error instanceof BackendClientError
    ? error.uiError
    : normalizeUiError(error, "transport");
}

export function protocolMismatch(message: string): BackendClientError {
  return new BackendClientError({
    code: "PROTOCOL_INVALID",
    message,
    retryable: true,
    source: "protocol",
  });
}
