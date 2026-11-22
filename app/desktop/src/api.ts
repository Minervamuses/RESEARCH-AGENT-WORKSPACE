// The only module that calls the backend and the native pickers: one typed
// function per protocol method the UI uses. Parameter and result types come
// from `MethodParams` and `MethodResults` in protocol.ts, and the result echo
// checks (U1) live here.
import { invoke } from "@tauri-apps/api/core";

import {
  BackendClientError,
  createBackendClient,
  normalizeUiError,
  type BackendClient,
} from "./backend.ts";
import {
  echoedIdFields,
  type EventData,
  type JsonObject,
  type MethodParams,
  type MethodResults,
  type ProtocolMethod,
  type SessionCreatedDto,
} from "./protocol.ts";

/** The backend client surface the api uses; tests inject a fake. */
export type ApiBackend = Pick<BackendClient, "requestTracked" | "initialize" | "start" | "restart" | "shutdown">;

/** The native Tauri commands behind the file and folder pickers. */
export type NativeInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export interface TrackedCall<T> {
  requestId: string;
  result: Promise<T>;
}

type ResultMethod = keyof MethodResults;

function echoMismatch(message: string): BackendClientError {
  return new BackendClientError(normalizeUiError(new Error(message), "protocol"));
}

/**
 * A result must echo the logical identifiers its request carried. This keeps a
 * late response from an ended operation from being applied to the current view.
 * The compared fields come from the contract (`echoedIdFields`): ids both the
 * method's params and result schema declare, compared only when the request
 * carried the field and the result returned it.
 */
function verifyResultEcho(method: ProtocolMethod, params: JsonObject, data: JsonObject): void {
  for (const field of echoedIdFields(method)) {
    if (field in params && field in data && data[field] !== params[field]) {
      throw echoMismatch(`data.${field} must match params.${field}`);
    }
  }
}

/** Typed view of a request event's data; `tests/protocol_types.test.ts` ties `EventData` to the contract. */
export function eventData<E extends keyof EventData>(_event: E, data: JsonObject): EventData[E] {
  return data as unknown as EventData[E];
}

export function createApi(backend: ApiBackend, nativeInvoke: NativeInvoke) {
  function tracked<M extends ResultMethod>(
    method: M,
    params: MethodParams[M],
    check?: (params: MethodParams[M], data: MethodResults[M]) => void,
  ): TrackedCall<MethodResults[M]> {
    // DTO interfaces have no index signature; the wire params are plain JSON.
    const wire = params as unknown as JsonObject;
    const { requestId, result } = backend.requestTracked(method, wire);
    return {
      requestId,
      result: result.then((data) => {
        verifyResultEcho(method, wire, data);
        const typed = data as unknown as MethodResults[M];
        check?.(params, typed);
        return typed;
      }),
    };
  }

  async function call<M extends ResultMethod>(
    method: M,
    params: MethodParams[M],
    check?: (params: MethodParams[M], data: MethodResults[M]) => void,
  ): Promise<MethodResults[M]> {
    return tracked(method, params, check).result;
  }

  return {
    // Backend lifecycle.
    initialize: backend.initialize,
    start: backend.start,
    restart: backend.restart,
    shutdown: backend.shutdown,

    // Native pickers.
    pickProject: (initialPath: string | null) =>
      nativeInvoke<string | null>("pick_project", { initialPath }),
    pickDocument: (rootPath: string) =>
      nativeInvoke<string | null>("pick_document", { rootPath }),

    // Runtime and workspace.
    runtimeDiagnostics: () => call("runtime.diagnostics", {}),
    workspaceSelect: (params: MethodParams["workspace.select"]) => call("workspace.select", params),

    // Documents.
    documentOpen: (params: MethodParams["document.open"]) => call("document.open", params),
    documentSave: (params: MethodParams["document.save"]) => call("document.save", params),
    documentApplyTracked: (params: MethodParams["document.apply"]) => tracked("document.apply", params),

    // Sessions.
    sessionCreate: (params: MethodParams["session.create"]) => call("session.create", params),
    /** Also checks that the page offset is the requested one (load-more pages). */
    sessionList: (params: MethodParams["session.list"]) =>
      call("session.list", params, (sent, data) => {
        if (sent.offset !== undefined && data.offset !== sent.offset) {
          throw echoMismatch("The backend returned a mismatched conversation page.");
        }
      }),
    sessionSelect: (params: MethodParams["session.select"]) => call("session.select", params),
    /** Also requires the deleted status. */
    sessionDelete: (params: MethodParams["session.delete"]) =>
      call("session.delete", params, (_sent, data) => {
        if (data.status !== "deleted") {
          throw echoMismatch("The backend deleted a different conversation.");
        }
      }),
    sessionRename: (params: MethodParams["session.rename"]) => call("session.rename", params),
    sessionTranscript: (params: MethodParams["session.transcript"]) => call("session.transcript", params),
    sessionTurnTracked: (params: MethodParams["session.turn"]) => tracked("session.turn", params),
    sessionStop: (params: MethodParams["session.stop"]) => call("session.stop", params),
    sessionSetPermission: (params: MethodParams["session.set_permission"]) =>
      call("session.set_permission", params),
    /**
     * The contract has no result schema for `session.set_thinking`; the backend
     * answers with the session summary, which `SessionCreatedDto` describes.
     */
    sessionSetThinking: async (params: MethodParams["session.set_thinking"]): Promise<SessionCreatedDto> => {
      const wire = params as unknown as JsonObject;
      const data = await backend.requestTracked("session.set_thinking", wire).result;
      verifyResultEcho("session.set_thinking", wire, data);
      return data as unknown as SessionCreatedDto;
    },

    // Extensions.
    extensionsPreview: () => call("extensions.preview", {}),
    extensionsApply: (params: MethodParams["extensions.apply"]) => call("extensions.apply", params),

    // Approvals. Also requires the resolved approval to be the requested one.
    approvalResolve: (params: MethodParams["approval.resolve"]) =>
      call("approval.resolve", params, (sent, data) => {
        if (data.approvalId !== sent.approvalId) {
          throw echoMismatch("The backend resolved a different approval request.");
        }
      }),

    // Bibliography.
    bibliographyInspect: (params: MethodParams["bibliography.inspect"]) => call("bibliography.inspect", params),
    bibliographyRender: (params: MethodParams["bibliography.render"]) => call("bibliography.render", params),
    bibliographySetStyle: (params: MethodParams["bibliography.set_style"]) =>
      call("bibliography.set_style", params),
    bibliographyRemove: (params: MethodParams["bibliography.remove"]) => call("bibliography.remove", params),
    bibliographyAddTracked: (params: MethodParams["bibliography.add"]) => tracked("bibliography.add", params),
    bibliographyExport: (params: MethodParams["bibliography.export"]) => call("bibliography.export", params),
  };
}

export type Api = ReturnType<typeof createApi>;

const nativeInvoke: NativeInvoke = <T>(command: string, args?: Record<string, unknown>) => invoke<T>(command, args);

export const api: Api = createApi(createBackendClient({ invoke: nativeInvoke }), nativeInvoke);
