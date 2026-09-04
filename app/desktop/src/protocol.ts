export const PROTOCOL_VERSION = 1 as const;
export const MAX_PROTOCOL_LINE_BYTES = 2 * 1024 * 1024;
export const MAX_REQUEST_ID_BYTES = 128;
export const MAX_ERROR_MESSAGE_BYTES = 4096;

export const PROTOCOL_METHODS = [
  "runtime.diagnostics",
  "project.list",
  "session.create",
  "session.list",
  "session.select",
  "session.retry_registration",
  "session.transcript",
  "session.status",
  "session.turn",
  "session.set_mode",
  "session.set_thinking",
  "session.shutdown",
  "knowledge.overview",
  "knowledge.search",
  "knowledge.list_chunks",
  "knowledge.get_context",
  "knowledge.init_workspace",
  "knowledge.ingest_file",
  "knowledge.ingest_folder",
  "knowledge.sync",
  "knowledge.prune_preview",
  "knowledge.prune_apply",
  "extensions.status",
  "extensions.preview",
  "extensions.apply",
  "approval.resolve",
  "runtime.shutdown",
] as const;

export const REQUEST_EVENTS = [
  "request.started",
  "request.progress",
  "stage.changed",
  "tool.started",
  "tool.finished",
  "tool.failed",
  "approval.required",
  "knowledge.progress",
  "shutdown.progress",
  "collecting.started",
  "collecting.completed",
  "tagging.started",
  "tagging.folder_completed",
  "metadata.written",
  "writing.started",
  "writing.file_completed",
  "ingest.completed",
  "ingest.failed",
] as const;

export const PROCESS_EVENTS = [
  "backend.ready",
  "backend.crashed",
  "backend.shutting_down",
  "backend.protocol_error",
] as const;

export const PROTOCOL_ERROR_CODES = [
  "PROTOCOL_INVALID",
  "PROTOCOL_VERSION_UNSUPPORTED",
  "RUNTIME_WRONG_CONDA_ENV",
  "SESSION_NOT_READY",
  "OPENROUTER_NOT_CONFIGURED",
  "OLLAMA_UNREACHABLE",
  "OLLAMA_MODEL_MISSING",
  "GRAPH_LIMIT_REACHED",
  "BUSY_TURN",
  "BUSY_KNOWLEDGE_MUTATION",
  "BUSY_EXTENSION_OPERATION",
  "INVALID_PATH",
  "RAG_READ_FAILED",
  "RAG_WRITE_FAILED",
  "RAG_PARTIAL_WRITE_POSSIBLE",
  "PRUNE_PREVIEW_STALE",
  "EXTENSION_PREVIEW_FAILED",
  "EXTENSION_APPLY_FAILED",
  "APPROVAL_DENIED",
  "PROVIDER_RATE_LIMITED",
  "PROVIDER_REQUEST_FAILED",
  "INTERNAL_ERROR",
] as const;

export type JsonObject = Record<string, unknown>;
export type ProtocolMethod = (typeof PROTOCOL_METHODS)[number];
export type RequestEvent = (typeof REQUEST_EVENTS)[number];
export type ProcessEvent = (typeof PROCESS_EVENTS)[number];
export type ProtocolErrorCode = (typeof PROTOCOL_ERROR_CODES)[number];
export type ProtocolOrigin = "python" | "rust";

const TOOL_EVENT_DATA_KEYS = ["name", "callId", "status", "candidateId"] as const;
const TOOL_STATUSES = ["started", "ok", "failed", "denied"] as const;

export interface FieldRule {
  type:
    | "string"
    | "nullableString"
    | "boolean"
    | "nullableBoolean"
    | "integer"
    | "stringArray"
    | "objectArray"
    | "requestId"
    | "turnId"
    | "utcTimestamp";
  required: boolean;
  maxBytes?: number;
  minimum?: number;
  maximum?: number;
  maxItems?: number;
  itemMaxBytes?: number;
  enum?: readonly string[];
  items?: FieldSchema;
}

export type FieldSchema = Record<string, FieldRule>;

export const TURN_ERROR_DETAILS_SCHEMA: FieldSchema = {
  turnId: { type: "turnId", required: true },
  state: {
    type: "nullableString",
    required: true,
    enum: ["pending", "completed", "failed", "interrupted"],
  },
  accepted: { type: "boolean", required: true },
  persisted: { type: "boolean", required: true },
};

export const PROCESS_EVENT_ORIGINS: Record<ProcessEvent, readonly ProtocolOrigin[]> = {
  "backend.ready": ["python"],
  "backend.crashed": ["rust"],
  "backend.shutting_down": ["python", "rust"],
  "backend.protocol_error": ["python", "rust"],
};

export const FORBIDDEN_DATA_KEY_FRAGMENTS = [
  "apikey",
  "authorization",
  "langchain",
  "messages",
  "rawpayload",
  "rawprovider",
  "responsemetadata",
  "secret",
  "token",
  "toolargs",
  "toolcalls",
  "toolresult",
  "traceback",
  "turnlogs",
] as const;

export const EVENT_DATA_SCHEMAS: Partial<Record<RequestEvent, FieldSchema>> = {
  "approval.required": {
    approvalId: { type: "string", required: true, maxBytes: 256 },
    parentRequestId: { type: "requestId", required: true },
    turnId: { type: "string", required: true, maxBytes: 256 },
    command: { type: "string", required: true, maxBytes: 65_536 },
    description: { type: "string", required: true, maxBytes: 4_096 },
    executionTimeoutSeconds: { type: "integer", required: true, minimum: 1, maximum: 3_600 },
    createdAt: { type: "utcTimestamp", required: true },
    expiresAt: { type: "utcTimestamp", required: true },
  },
  "collecting.started": {},
  "collecting.completed": {
    folders: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    files: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
  },
  "tagging.started": {
    total: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
  },
  "tagging.folder_completed": {
    completed: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    total: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    folder: { type: "string", required: true, maxBytes: 8_192 },
  },
  "metadata.written": {
    path: { type: "string", required: true, maxBytes: 8_192 },
  },
  "writing.started": {},
  "writing.file_completed": {
    filePath: { type: "string", required: true, maxBytes: 8_192 },
    chunks: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    filesCompleted: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
  },
  "ingest.completed": {
    files: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    chunks: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
  },
  "ingest.failed": {
    stage: { type: "string", required: true, maxBytes: 256 },
    partialWritePossible: { type: "boolean", required: true },
  },
};

export const RESULT_DATA_SCHEMAS: Partial<Record<ProtocolMethod, FieldSchema>> = {
  "runtime.diagnostics": {
    backendState: {
      type: "string",
      required: true,
      enum: ["starting", "ready", "shutting_down", "stopped", "crashed"],
    },
    platform: { type: "string", required: true, enum: ["linux"] },
    appRoot: { type: "string", required: true, maxBytes: 8_192 },
    workingDirectory: { type: "string", required: true, maxBytes: 8_192 },
    originalWorkingDirectory: { type: "string", required: true, maxBytes: 8_192 },
    pythonVersion: { type: "string", required: true, maxBytes: 256 },
    sysPrefix: { type: "string", required: true, maxBytes: 8_192 },
    condaEnvironment: { type: "nullableString", required: true, maxBytes: 256 },
    condaPrefix: { type: "nullableString", required: true, maxBytes: 8_192 },
    protocolVersion: { type: "integer", required: true, minimum: 1, maximum: 1 },
    backendVersion: { type: "string", required: true, maxBytes: 256 },
    openRouterConfigured: { type: "boolean", required: true },
    openAlexConfigured: { type: "boolean", required: true },
    storePath: { type: "string", required: true, maxBytes: 8_192 },
    citationOutputPath: { type: "string", required: true, maxBytes: 8_192 },
    ollamaReachable: { type: "nullableBoolean", required: true },
    ollamaModelAvailable: { type: "nullableBoolean", required: true },
    mcpEnabled: { type: "boolean", required: true },
    mcpFamilies: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 256,
    },
    mcpDiagnostics: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 4_096,
    },
  },
  "session.create": {
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    graphRecursionLimit: {
      type: "integer",
      required: true,
      minimum: 3,
      maximum: 0xffff_ffff,
    },
    planMode: { type: "boolean", required: true },
    planLogPath: { type: "nullableString", required: true, maxBytes: 8_192 },
    thinkingMode: { type: "string", required: true, enum: ["normal", "extended"] },
    loadedSkills: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 256,
    },
    mcpFamilies: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 256,
    },
    startupDiagnostics: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 4_096,
    },
    extensionRevision: {
      type: "integer",
      required: true,
      minimum: 0,
      maximum: 0xffff_ffff,
    },
    projectId: { type: "string", required: false, maxBytes: 256 },
    registered: { type: "boolean", required: false },
  },
  "session.turn": {
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnId: { type: "turnId", required: true },
    turnNumber: { type: "integer", required: true, minimum: 1, maximum: 4_096 },
    state: { type: "string", required: true, enum: ["completed"] },
    accepted: { type: "boolean", required: true },
    persisted: { type: "boolean", required: true },
    text: { type: "string", required: true, maxBytes: 2_097_152 },
    validationErrors: {
      type: "stringArray",
      required: true,
      maxItems: 128,
      itemMaxBytes: 4_096,
    },
    toolSummaries: {
      type: "objectArray",
      required: true,
      maxItems: 512,
      items: {
        name: { type: "string", required: true, maxBytes: 256 },
        status: { type: "string", required: true, enum: ["ok", "failed", "denied"] },
        callId: { type: "string", required: false, maxBytes: 256 },
        candidateId: { type: "string", required: false, maxBytes: 256 },
      },
    },
    responseKind: { type: "string", required: false, enum: ["answer", "command"] },
    streamKind: { type: "string", required: false, enum: ["final_only"] },
    chunkCount: { type: "integer", required: false, minimum: 0, maximum: 0 },
    registrationStatus: {
      type: "string",
      required: false,
      enum: ["registered", "pending", "not_required"],
    },
    registrationIssue: { type: "nullableString", required: false, maxBytes: 4_096 },
    extensionAction: { type: "string", required: false, enum: ["status", "preview"] },
  },
  "session.shutdown": {
    status: { type: "string", required: true, enum: ["stopped", "no_session"] },
  },
  "runtime.shutdown": {
    status: { type: "string", required: true, enum: ["stopped", "no_session"] },
  },
  "project.list": {
    status: { type: "string", required: true, enum: ["ready", "unavailable"] },
    issue: { type: "nullableString", required: true, maxBytes: 4_096 },
    projects: {
      type: "objectArray",
      required: true,
      maxItems: 50,
      items: {
        projectId: { type: "string", required: true, maxBytes: 256 },
        name: { type: "string", required: true, maxBytes: 256 },
        sessionCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
      },
    },
    selectedProjectId: { type: "nullableString", required: true, maxBytes: 256 },
    selectedSessionId: { type: "nullableString", required: true, maxBytes: 32 },
  },
  "session.list": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    status: { type: "string", required: true, enum: ["ready", "unavailable"] },
    issue: { type: "nullableString", required: true, maxBytes: 4_096 },
    items: {
      type: "objectArray",
      required: true,
      maxItems: 50,
      items: {
        sessionId: { type: "string", required: true, maxBytes: 32 },
        title: { type: "string", required: true, maxBytes: 256 },
        turnCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
        createdAt: { type: "nullableString", required: true, maxBytes: 64 },
        updatedAt: { type: "nullableString", required: true, maxBytes: 64 },
        status: { type: "string", required: true, enum: ["ready", "degraded", "unavailable"] },
        issue: { type: "nullableString", required: true, maxBytes: 4_096 },
      },
    },
    total: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    offset: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    limit: { type: "integer", required: true, minimum: 1, maximum: 50 },
    hasMore: { type: "boolean", required: true },
  },
  "session.select": {
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    graphRecursionLimit: { type: "integer", required: true, minimum: 3, maximum: 0xffff_ffff },
    planMode: { type: "boolean", required: true },
    planLogPath: { type: "nullableString", required: true, maxBytes: 8_192 },
    thinkingMode: { type: "string", required: true, enum: ["normal", "extended"] },
    loadedSkills: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 256 },
    mcpFamilies: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 256 },
    startupDiagnostics: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 4_096 },
    extensionRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    projectId: { type: "string", required: true, maxBytes: 256 },
    registered: { type: "boolean", required: true },
  },
  "session.retry_registration": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
    status: { type: "string", required: true, enum: ["registered", "pending"] },
    issue: { type: "nullableString", required: true, maxBytes: 4_096 },
  },
  "session.transcript": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
    status: { type: "string", required: true, enum: ["ready", "degraded", "unavailable"] },
    issue: { type: "nullableString", required: true, maxBytes: 4_096 },
    items: {
      type: "objectArray",
      required: true,
      maxItems: 20,
      items: {
        turnId: { type: "turnId", required: true },
        turnNumber: { type: "integer", required: true, minimum: 1, maximum: 0xffff_ffff },
        kind: {
          type: "string",
          required: true,
          enum: ["conversational", "display-only"],
        },
        state: {
          type: "string",
          required: true,
          enum: ["pending", "completed", "failed", "interrupted"],
        },
        timestamp: { type: "utcTimestamp", required: true },
        userText: { type: "string", required: true, maxBytes: 32_768 },
        assistantText: { type: "nullableString", required: true, maxBytes: 32_768 },
        failureCode: {
          type: "nullableString",
          required: true,
          maxBytes: 256,
          enum: ["execution_failed", "persistence_failed", "interrupted", "cancelled"],
        },
        failureMessage: { type: "nullableString", required: true, maxBytes: 4_096 },
        failureRetryable: { type: "nullableBoolean", required: true },
        toolActivities: {
          type: "objectArray",
          required: true,
          maxItems: 128,
          items: {
            callId: { type: "nullableString", required: true, maxBytes: 256 },
            name: { type: "string", required: true, maxBytes: 256 },
            arguments: { type: "string", required: true, maxBytes: 32_768 },
            result: { type: "string", required: true, maxBytes: 65_536 },
            status: {
              type: "string",
              required: true,
              enum: ["ok", "failed", "denied", "incomplete"],
            },
            promptEligible: { type: "boolean", required: true },
          },
        },
      },
    },
    total: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    offset: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    limit: { type: "integer", required: true, minimum: 1, maximum: 20 },
    hasMore: { type: "boolean", required: true },
  },
  "extensions.status": {
    dropinRoot: { type: "string", required: true, maxBytes: 8_192 },
    stateRoot: { type: "string", required: true, maxBytes: 8_192 },
    desiredCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    appliedCount: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    appliedRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    runningRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    restartRequired: { type: "boolean", required: true },
    managerAvailable: { type: "boolean", required: true },
    managerError: { type: "nullableString", required: true, maxBytes: 4_096 },
    diagnostics: { type: "stringArray", required: true, maxItems: 128, itemMaxBytes: 4_096 },
    runningMcpFamilies: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 256 },
  },
  "extensions.preview": {
    previewId: { type: "string", required: true, maxBytes: 256 },
    summary: { type: "string", required: true, maxBytes: 4_096 },
    proposedSkills: {
      type: "stringArray",
      required: true,
      maxItems: 512,
      itemMaxBytes: 256,
    },
    bindings: {
      type: "objectArray",
      required: true,
      maxItems: 512,
      items: {
        name: { type: "string", required: true, maxBytes: 256 },
        server: { type: "string", required: true, maxBytes: 256 },
        bindingHash: { type: "string", required: true, maxBytes: 256 },
        requiresApproval: { type: "boolean", required: true },
        command: { type: "string", required: true, maxBytes: 8_192 },
        arguments: { type: "stringArray", required: true, maxItems: 128, itemMaxBytes: 4_096 },
        workingDirectory: { type: "string", required: true, maxBytes: 8_192 },
        environmentNames: { type: "stringArray", required: true, maxItems: 128, itemMaxBytes: 256 },
      },
    },
  },
  "extensions.apply": {
    previousRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    appliedRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    restartRequired: { type: "boolean", required: true },
    items: {
      type: "objectArray",
      required: true,
      maxItems: 512,
      items: {
        key: { type: "string", required: true, maxBytes: 256 },
        outcome: {
          type: "string",
          required: true,
          enum: ["added", "updated", "removed", "unchanged", "blocked", "pending_approval"],
        },
        detail: { type: "string", required: true, maxBytes: 4_096 },
      },
    },
    diagnostics: { type: "stringArray", required: true, maxItems: 128, itemMaxBytes: 4_096 },
  },
  "approval.resolve": {
    approvalId: { type: "string", required: true, maxBytes: 256 },
    approved: { type: "boolean", required: true },
  },
};

export const METHOD_PARAM_SCHEMAS: Record<ProtocolMethod, FieldSchema> = {
  "runtime.diagnostics": {},
  "project.list": {},
  "session.create": {
    loadMcp: { type: "boolean", required: false },
    graphRecursionLimit: {
      type: "integer",
      required: false,
      minimum: 3,
      maximum: 0xffff_ffff,
    },
    projectId: { type: "string", required: false, maxBytes: 256 },
  },
  "session.list": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    offset: { type: "integer", required: false, minimum: 0, maximum: 0xffff_ffff },
    limit: { type: "integer", required: false, minimum: 1, maximum: 50 },
  },
  "session.select": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
  },
  "session.retry_registration": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
  },
  "session.transcript": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
    offset: { type: "integer", required: false, minimum: 0, maximum: 0xffff_ffff },
    limit: { type: "integer", required: false, minimum: 1, maximum: 20 },
  },
  "session.status": {},
  "session.turn": {
    text: { type: "string", required: true, maxBytes: 1_048_576 },
    turnId: { type: "turnId", required: true },
    retry: { type: "boolean", required: true },
  },
  "session.set_mode": {
    mode: { type: "string", required: true, enum: ["normal", "plan"] },
  },
  "session.set_thinking": {
    mode: { type: "string", required: true, enum: ["normal", "extended"] },
  },
  "session.shutdown": {},
  "knowledge.overview": {},
  "knowledge.search": {
    query: { type: "string", required: true, maxBytes: 16_384 },
    k: { type: "integer", required: false, minimum: 1, maximum: 20 },
    folderPrefix: { type: "string", required: false, maxBytes: 8_192 },
    category: { type: "string", required: false, maxBytes: 256 },
    fileType: { type: "string", required: false, maxBytes: 64 },
    dateFrom: { type: "string", required: false, maxBytes: 10 },
    dateTo: { type: "string", required: false, maxBytes: 10 },
  },
  "knowledge.list_chunks": {
    folderPrefix: { type: "string", required: false, maxBytes: 8_192 },
    pid: { type: "string", required: false, maxBytes: 1_024 },
    category: { type: "string", required: false, maxBytes: 256 },
    fileType: { type: "string", required: false, maxBytes: 64 },
    dateFrom: { type: "string", required: false, maxBytes: 10 },
    dateTo: { type: "string", required: false, maxBytes: 10 },
    offset: { type: "integer", required: false, minimum: 0, maximum: 0xffff_ffff },
    limit: { type: "integer", required: false, minimum: 1, maximum: 100 },
  },
  "knowledge.get_context": {
    pid: { type: "string", required: true, maxBytes: 1_024 },
    chunkId: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    window: { type: "integer", required: false, minimum: 0, maximum: 3 },
  },
  "knowledge.init_workspace": {},
  "knowledge.ingest_file": {
    path: { type: "string", required: true, maxBytes: 8_192 },
  },
  "knowledge.ingest_folder": {
    path: { type: "string", required: true, maxBytes: 8_192 },
  },
  "knowledge.sync": {
    path: { type: "string", required: true, maxBytes: 8_192 },
  },
  "knowledge.prune_preview": {
    path: { type: "string", required: true, maxBytes: 8_192 },
  },
  "knowledge.prune_apply": {
    previewId: { type: "string", required: true, maxBytes: 256 },
  },
  "extensions.status": {},
  "extensions.preview": {},
  "extensions.apply": {
    previewId: { type: "string", required: true, maxBytes: 256 },
    approvedBindingHashes: { type: "stringArray", required: true, maxItems: 512 },
  },
  "approval.resolve": {
    approvalId: { type: "string", required: true, maxBytes: 256 },
    parentRequestId: { type: "requestId", required: false },
    turnId: { type: "string", required: false, maxBytes: 256 },
    approved: { type: "boolean", required: true },
  },
  "runtime.shutdown": {},
};

export const METHOD_REQUIRED_PARAMS = Object.fromEntries(
  Object.entries(METHOD_PARAM_SCHEMAS).map(([method, schema]) => [
    method,
    Object.entries(schema)
      .filter(([, rule]) => rule.required)
      .map(([field]) => field),
  ]),
) as unknown as Record<ProtocolMethod, readonly string[]>;

export interface ProtocolErrorDto {
  code: ProtocolErrorCode;
  message: string;
  retryable: boolean;
  details: JsonObject;
}

export interface TurnLifecycleDetailsDto {
  turnId: string;
  state: "pending" | "completed" | "failed" | "interrupted" | null;
  accepted: boolean;
  persisted: boolean;
}

export interface ToolSummaryDto {
  name: string;
  status: "ok" | "failed" | "denied";
  callId?: string;
  candidateId?: string;
}

export interface TurnCompletedDto {
  sessionId: string;
  turnId: string;
  turnNumber: number;
  state: "completed";
  accepted: boolean;
  persisted: boolean;
  text: string;
  validationErrors: string[];
  toolSummaries: ToolSummaryDto[];
  responseKind?: "answer" | "command";
  streamKind?: "final_only";
  chunkCount?: number;
  registrationStatus?: "registered" | "pending" | "not_required";
  registrationIssue?: string | null;
  extensionAction?: "status" | "preview";
}

export interface SessionCreatedDto {
  sessionId: string;
  turnCount: number;
  graphRecursionLimit: number;
  planMode: boolean;
  planLogPath: string | null;
  thinkingMode: "normal" | "extended";
  loadedSkills: string[];
  mcpFamilies: string[];
  startupDiagnostics: string[];
  extensionRevision: number;
  projectId?: string;
  registered?: boolean;
}

export interface ProjectSummaryDto {
  projectId: string;
  name: string;
  sessionCount: number;
}

export interface ProjectListDto {
  status: "ready" | "unavailable";
  issue: string | null;
  projects: ProjectSummaryDto[];
  selectedProjectId: string | null;
  selectedSessionId: string | null;
}

export interface SessionSummaryDto {
  sessionId: string;
  title: string;
  turnCount: number;
  createdAt: string | null;
  updatedAt: string | null;
  status: "ready" | "degraded" | "unavailable";
  issue: string | null;
}

export interface SessionListDto {
  projectId: string;
  status: "ready" | "unavailable";
  issue: string | null;
  items: SessionSummaryDto[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
}

export interface SessionSelectedDto extends SessionCreatedDto {
  projectId: string;
  registered: boolean;
}

export interface RegistrationRetryDto {
  projectId: string;
  sessionId: string;
  status: "registered" | "pending";
  issue: string | null;
}

export interface ToolActivityDto {
  callId: string | null;
  name: string;
  arguments: string;
  result: string;
  status: "ok" | "failed" | "denied" | "incomplete";
  promptEligible: boolean;
}

export interface TranscriptTurnDto {
  turnId: string;
  turnNumber: number;
  kind: "conversational" | "display-only";
  state: "pending" | "completed" | "failed" | "interrupted";
  timestamp: string;
  userText: string;
  assistantText: string | null;
  failureCode: "execution_failed" | "persistence_failed" | "interrupted" | "cancelled" | null;
  failureMessage: string | null;
  failureRetryable: boolean | null;
  toolActivities: ToolActivityDto[];
}

export interface SessionTranscriptDto {
  projectId: string;
  sessionId: string;
  status: "ready" | "degraded" | "unavailable";
  issue: string | null;
  items: TranscriptTurnDto[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
}

export interface RuntimeDiagnosticsDto {
  backendState: "starting" | "ready" | "shutting_down" | "stopped" | "crashed";
  platform: "linux";
  appRoot: string;
  workingDirectory: string;
  originalWorkingDirectory: string;
  pythonVersion: string;
  sysPrefix: string;
  condaEnvironment: string | null;
  condaPrefix: string | null;
  protocolVersion: 1;
  backendVersion: string;
  openRouterConfigured: boolean;
  openAlexConfigured: boolean;
  storePath: string;
  citationOutputPath: string;
  ollamaReachable: boolean | null;
  ollamaModelAvailable: boolean | null;
  mcpEnabled: boolean;
  mcpFamilies: string[];
  mcpDiagnostics: string[];
}

export interface ExtensionBindingDto {
  name: string;
  server: string;
  bindingHash: string;
  requiresApproval: boolean;
  command: string;
  arguments: string[];
  workingDirectory: string;
  environmentNames: string[];
}

export interface ExtensionPreviewDto {
  previewId: string;
  summary: string;
  proposedSkills: string[];
  bindings: ExtensionBindingDto[];
}

export interface ExtensionApplyItemDto {
  key: string;
  outcome: "added" | "updated" | "removed" | "unchanged" | "blocked" | "pending_approval";
  detail: string;
}

export interface ExtensionApplyDto {
  previousRevision: number;
  appliedRevision: number;
  restartRequired: boolean;
  items: ExtensionApplyItemDto[];
  diagnostics: string[];
}

export interface ApprovalRequiredDto {
  approvalId: string;
  parentRequestId: string;
  turnId: string;
  command: string;
  description: string;
  executionTimeoutSeconds: number;
  createdAt: string;
  expiresAt: string;
}

export interface ApprovalResolvedDto {
  approvalId: string;
  approved: boolean;
}

interface EnvelopeBase {
  protocolVersion: typeof PROTOCOL_VERSION;
}

export interface RequestEnvelope extends EnvelopeBase {
  messageType: "request";
  requestId: string;
  method: ProtocolMethod;
  params: JsonObject;
}

export interface RequestEventEnvelope extends EnvelopeBase {
  messageType: "event";
  requestId: string;
  sequence: number;
  event: RequestEvent;
  data: JsonObject;
}

export interface ProcessEventEnvelope extends EnvelopeBase {
  messageType: "event";
  event: ProcessEvent;
  data: JsonObject;
}

export interface SuccessEnvelope extends EnvelopeBase {
  messageType: "result";
  requestId: string;
  ok: true;
  data: JsonObject;
}

export interface FailureEnvelope extends EnvelopeBase {
  messageType: "result";
  requestId: string;
  ok: false;
  error: ProtocolErrorDto;
}

export type EventEnvelope = RequestEventEnvelope | ProcessEventEnvelope;
export type ResultEnvelope = SuccessEnvelope | FailureEnvelope;
export type ProtocolMessage = RequestEnvelope | EventEnvelope | ResultEnvelope;

type ProtocolValidationCode = "PROTOCOL_INVALID" | "PROTOCOL_VERSION_UNSUPPORTED";

export class ProtocolContractError extends Error {
  readonly code: ProtocolValidationCode;

  constructor(code: ProtocolValidationCode, message: string) {
    super(message);
    this.name = "ProtocolContractError";
    this.code = code;
  }
}

const encoder = new TextEncoder();
const requestIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const turnIdPattern = /^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$/;

function invalid(message: string): never {
  throw new ProtocolContractError("PROTOCOL_INVALID", message);
}

function expectObject(value: unknown, field: string): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    invalid(`${field} must be a JSON object`);
  }
  return value as JsonObject;
}

function expectString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    invalid(`${field} must be a non-empty string`);
  }
  return value;
}

function expectExactKeys(value: JsonObject, allowed: readonly string[], field: string): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      invalid(`${field} contains unknown field: ${key}`);
    }
  }
}

function expectInteger(value: unknown, field: string, minimum?: number, maximum?: number): number {
  if (!Number.isInteger(value)) {
    invalid(`${field} must be an integer`);
  }
  const integer = Number(value);
  if (minimum !== undefined && integer < minimum) {
    invalid(`${field} must be at least ${minimum}`);
  }
  if (maximum !== undefined && integer > maximum) {
    invalid(`${field} must be at most ${maximum}`);
  }
  return integer;
}

function expectRequestId(value: unknown): string {
  const requestId = expectString(value, "requestId");
  if (encoder.encode(requestId).byteLength > MAX_REQUEST_ID_BYTES) {
    invalid("requestId is too large");
  }
  if (!requestIdPattern.test(requestId)) {
    invalid("requestId must be a canonical UUID");
  }
  return requestId;
}

function expectTurnId(value: unknown, field: string): string {
  const turnId = expectString(value, field);
  if (!turnIdPattern.test(turnId)) {
    invalid(`${field} must be a canonical UUIDv4 hex value`);
  }
  return turnId;
}

const utcTimestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?Z$/;

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function isValidUtcTimestamp(value: string): boolean {
  const match = utcTimestampPattern.exec(value);
  if (match === null) {
    return false;
  }
  const [year, month, day, hour, minute, second] = match
    .slice(1)
    .map((part) => Number(part));
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
    return false;
  }
  const days = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= days[month - 1];
}

function validateFieldRule(value: unknown, rule: FieldRule, field: string): void {
  if (rule.type === "string") {
    const text = expectString(value, field);
    if (rule.maxBytes !== undefined && encoder.encode(text).byteLength > rule.maxBytes) {
      invalid(`${field} is too large`);
    }
    if (rule.enum !== undefined && !rule.enum.includes(text)) {
      invalid(`${field} contains an unknown enum value: ${text}`);
    }
    return;
  }
  if (rule.type === "nullableString") {
    if (value !== null) {
      validateFieldRule(value, { ...rule, type: "string" }, field);
    }
    return;
  }
  if (rule.type === "boolean") {
    if (typeof value !== "boolean") {
      invalid(`${field} must be a boolean`);
    }
    return;
  }
  if (rule.type === "nullableBoolean") {
    if (value !== null && typeof value !== "boolean") {
      invalid(`${field} must be a boolean or null`);
    }
    return;
  }
  if (rule.type === "integer") {
    expectInteger(value, field, rule.minimum, rule.maximum);
    return;
  }
  if (rule.type === "stringArray") {
    if (!Array.isArray(value)) {
      invalid(`${field} must be an array`);
    }
    if (rule.maxItems !== undefined && value.length > rule.maxItems) {
      invalid(`${field} contains too many items`);
    }
    value.forEach((item, index) => {
      const text = expectString(item, `${field}[${index}]`);
      if (rule.itemMaxBytes !== undefined && encoder.encode(text).byteLength > rule.itemMaxBytes) {
        invalid(`${field}[${index}] is too large`);
      }
    });
    return;
  }
  if (rule.type === "objectArray") {
    if (!Array.isArray(value)) {
      invalid(`${field} must be an array`);
    }
    if (rule.maxItems !== undefined && value.length > rule.maxItems) {
      invalid(`${field} contains too many items`);
    }
    if (rule.items === undefined) {
      invalid(`${field} is missing its item schema`);
    }
    value.forEach((item, index) =>
      validateObjectSchema(expectObject(item, `${field}[${index}]`), rule.items!, `${field}[${index}]`),
    );
    return;
  }
  if (rule.type === "requestId") {
    expectRequestId(value);
    return;
  }
  if (rule.type === "turnId") {
    expectTurnId(value, field);
    return;
  }
  const timestamp = expectString(value, field);
  if (!isValidUtcTimestamp(timestamp)) {
    invalid(`${field} must be a UTC ISO 8601 timestamp`);
  }
}

function validateObjectSchema(value: JsonObject, schema: FieldSchema, field: string): void {
  expectExactKeys(value, Object.keys(schema), field);
  for (const [name, rule] of Object.entries(schema)) {
    if (!(name in value)) {
      if (rule.required) {
        invalid(`${field}.${name} is required`);
      }
      continue;
    }
    validateFieldRule(value[name], rule, `${field}.${name}`);
  }
}

export function parseTurnLifecycleDetails(value: unknown): TurnLifecycleDetailsDto {
  const details = expectObject(value, "error.details");
  validateObjectSchema(details, TURN_ERROR_DETAILS_SCHEMA, "error.details");
  const parsed: TurnLifecycleDetailsDto = {
    turnId: details.turnId as string,
    state: details.state as TurnLifecycleDetailsDto["state"],
    accepted: details.accepted as boolean,
    persisted: details.persisted as boolean,
  };
  if (parsed.state === null) {
    if (parsed.accepted || parsed.persisted) {
      invalid("a null turn error state must not be accepted or persisted");
    }
  } else if (!parsed.accepted || !parsed.persisted) {
    invalid("a durable turn error state must be accepted and persisted");
  }
  return parsed;
}

function normalizeDataKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function validateSafeData(value: unknown, field: string): void {
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateSafeData(item, `${field}[${index}]`));
    return;
  }
  if (typeof value !== "object" || value === null) {
    return;
  }
  for (const [key, item] of Object.entries(value)) {
    const normalized = normalizeDataKey(key);
    if (FORBIDDEN_DATA_KEY_FRAGMENTS.some((fragment) => normalized.includes(fragment))) {
      invalid(`${field} contains forbidden field: ${key}`);
    }
    validateSafeData(item, `${field}.${key}`);
  }
}

function includesValue<const T extends readonly string[]>(values: T, value: string): value is T[number] {
  return values.includes(value as T[number]);
}

function validateVersion(message: JsonObject): void {
  if (typeof message.protocolVersion !== "number") {
    invalid("protocolVersion is required");
  }
  if (message.protocolVersion !== PROTOCOL_VERSION) {
    throw new ProtocolContractError(
      "PROTOCOL_VERSION_UNSUPPORTED",
      `Unsupported protocol version: ${String(message.protocolVersion)}`,
    );
  }
}

function validateParams(method: ProtocolMethod, params: JsonObject): void {
  validateObjectSchema(params, METHOD_PARAM_SCHEMAS[method], "params");
}

export function validateResultData(method: ProtocolMethod, data: JsonObject): void {
  validateSafeData(data, "data");
  const schema = RESULT_DATA_SCHEMAS[method];
  if (schema !== undefined) {
    validateObjectSchema(data, schema, "data");
  }
  if (
    method === "session.turn" &&
    (data.state !== "completed" || data.accepted !== true || data.persisted !== true)
  ) {
    invalid("session.turn success must be durably completed");
  }
  if (method === "session.transcript") {
    (data.items as JsonObject[]).forEach((item) => {
      const failureValues = [
        item.failureCode,
        item.failureMessage,
        item.failureRetryable,
      ];
      if (item.state === "completed") {
        if (item.assistantText === null || failureValues.some((value) => value !== null)) {
          invalid("completed transcript turn has invalid lifecycle fields");
        }
        return;
      }
      if (item.state === "pending") {
        if (
          item.assistantText !== null ||
          failureValues.some((value) => value !== null) ||
          (item.toolActivities as unknown[]).length > 0
        ) {
          invalid("pending transcript turn has invalid lifecycle fields");
        }
        return;
      }
      if (
        item.assistantText !== null ||
        failureValues.some((value) => value === null) ||
        (item.toolActivities as unknown[]).length > 0
      ) {
        invalid(`${String(item.state)} transcript turn has invalid lifecycle fields`);
      }
      if (
        item.state === "failed" &&
        item.failureCode !== "execution_failed" &&
        item.failureCode !== "persistence_failed"
      ) {
        invalid("failed transcript turn has an invalid failure code");
      }
      if (
        item.state === "interrupted" &&
        item.failureCode !== "interrupted" &&
        item.failureCode !== "cancelled"
      ) {
        invalid("interrupted transcript turn has an invalid failure code");
      }
    });
  }
}

function parseRequest(message: JsonObject): RequestEnvelope {
  expectExactKeys(
    message,
    ["protocolVersion", "messageType", "requestId", "method", "params"],
    "request",
  );
  const requestId = expectRequestId(message.requestId);
  const method = expectString(message.method, "method");
  if (!includesValue(PROTOCOL_METHODS, method)) {
    invalid(`Unknown method: ${method}`);
  }
  const params = expectObject(message.params, "params");
  validateParams(method, params);
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageType: "request",
    requestId,
    method,
    params,
  };
}

function validateToolEvent(event: RequestEvent, data: JsonObject): void {
  if (!event.startsWith("tool.")) {
    return;
  }
  for (const key of Object.keys(data)) {
    if (!includesValue(TOOL_EVENT_DATA_KEYS, key)) {
      invalid(`Unsafe tool event field: ${key}`);
    }
  }
  expectString(data.name, "data.name");
  const status = expectString(data.status, "data.status");
  if (!includesValue(TOOL_STATUSES, status)) {
    invalid(`Unknown tool status: ${status}`);
  }
  if (data.callId !== undefined) {
    expectString(data.callId, "data.callId");
  }
  if (data.candidateId !== undefined) {
    expectString(data.candidateId, "data.candidateId");
  }
}

function validateEventData(event: RequestEvent, requestId: string, data: JsonObject): void {
  validateToolEvent(event, data);
  const schema = EVENT_DATA_SCHEMAS[event];
  if (schema !== undefined) {
    validateObjectSchema(data, schema, "data");
  }
  if (event === "approval.required" && data.parentRequestId !== requestId) {
    invalid("data.parentRequestId must match the event requestId");
  }
}

function parseEvent(message: JsonObject): EventEnvelope {
  const event = expectString(message.event, "event");
  const data = expectObject(message.data, "data");
  validateSafeData(data, "data");
  if (message.requestId === undefined) {
    expectExactKeys(message, ["protocolVersion", "messageType", "event", "data"], "event");
    if (message.sequence !== undefined) {
      invalid("Process events cannot carry a sequence");
    }
    if (!includesValue(PROCESS_EVENTS, event)) {
      invalid(`Unknown process event: ${event}`);
    }
    return {
      protocolVersion: PROTOCOL_VERSION,
      messageType: "event",
      event,
      data,
    };
  }

  const requestId = expectRequestId(message.requestId);
  expectExactKeys(
    message,
    ["protocolVersion", "messageType", "requestId", "sequence", "event", "data"],
    "event",
  );
  if (
    !Number.isInteger(message.sequence) ||
    Number(message.sequence) < 1 ||
    Number(message.sequence) > 0xffff_ffff
  ) {
    invalid("Request event sequence must be a positive integer");
  }
  if (!includesValue(REQUEST_EVENTS, event)) {
    invalid(`Unknown request event: ${event}`);
  }
  validateEventData(event, requestId, data);
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageType: "event",
    requestId,
    sequence: Number(message.sequence),
    event,
    data,
  };
}

function parseError(value: unknown): ProtocolErrorDto {
  const error = expectObject(value, "error");
  expectExactKeys(error, ["code", "message", "retryable", "details"], "error");
  const code = expectString(error.code, "error.code");
  if (!includesValue(PROTOCOL_ERROR_CODES, code)) {
    invalid(`Unknown error code: ${code}`);
  }
  if (typeof error.retryable !== "boolean") {
    invalid("error.retryable must be a boolean");
  }
  const message = expectString(error.message, "error.message");
  if (encoder.encode(message).byteLength > MAX_ERROR_MESSAGE_BYTES) {
    invalid("error.message is too large");
  }
  const details = expectObject(error.details, "error.details");
  validateSafeData(details, "error.details");
  const hasTurnLifecycleField = Object.keys(TURN_ERROR_DETAILS_SCHEMA)
    .some((key) => key in details);
  if (hasTurnLifecycleField) {
    parseTurnLifecycleDetails(details);
  } else if (code === "INTERNAL_ERROR" && Object.keys(details).length > 0) {
    invalid("INTERNAL_ERROR details must be empty");
  }
  return {
    code,
    message,
    retryable: error.retryable,
    details,
  };
}

function parseResult(message: JsonObject): ResultEnvelope {
  const requestId = expectRequestId(message.requestId);
  if (message.ok === true) {
    expectExactKeys(
      message,
      ["protocolVersion", "messageType", "requestId", "ok", "data"],
      "result",
    );
    if (message.error !== undefined) {
      invalid("Successful results cannot contain error");
    }
    return {
      protocolVersion: PROTOCOL_VERSION,
      messageType: "result",
      requestId,
      ok: true,
      data: (() => {
        const data = expectObject(message.data, "data");
        validateSafeData(data, "data");
        return data;
      })(),
    };
  }
  if (message.ok === false) {
    expectExactKeys(
      message,
      ["protocolVersion", "messageType", "requestId", "ok", "error"],
      "result",
    );
    if (message.data !== undefined) {
      invalid("Failed results cannot contain data");
    }
    return {
      protocolVersion: PROTOCOL_VERSION,
      messageType: "result",
      requestId,
      ok: false,
      error: parseError(message.error),
    };
  }
  return invalid("result.ok must be a boolean");
}

export function parseProtocolMessage(value: unknown): ProtocolMessage {
  const message = expectObject(value, "message");
  validateVersion(message);
  const messageType = expectString(message.messageType, "messageType");
  if (messageType === "request") {
    return parseRequest(message);
  }
  if (messageType === "event") {
    return parseEvent(message);
  }
  if (messageType === "result") {
    return parseResult(message);
  }
  return invalid(`Unknown messageType: ${messageType}`);
}

export function validateProcessEventOrigin(event: ProcessEvent, origin: ProtocolOrigin): void {
  if (!PROCESS_EVENT_ORIGINS[event].includes(origin)) {
    invalid(`${event} cannot originate from ${origin}`);
  }
}

export function parseProtocolMessageFromOrigin(
  value: unknown,
  origin: ProtocolOrigin,
): ProtocolMessage {
  const message = parseProtocolMessage(value);
  if (message.messageType === "event" && !("requestId" in message)) {
    validateProcessEventOrigin(message.event, origin);
  }
  return message;
}

export function parseProtocolLine(line: string): ProtocolMessage {
  if (encoder.encode(line).byteLength > MAX_PROTOCOL_LINE_BYTES) {
    invalid("Protocol line exceeds the 2 MiB limit");
  }
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    return invalid("Protocol line is not valid JSON");
  }
  return parseProtocolMessage(value);
}

interface RequestTraceState {
  nextSequence: number;
  terminal: boolean;
  method: ProtocolMethod;
  turnId: string | null;
}

export class ProtocolTraceValidator {
  private readonly requests = new Map<string, RequestTraceState>();

  accept(message: ProtocolMessage): void {
    if (message.messageType === "request") {
      if (this.requests.has(message.requestId)) {
        invalid(`Duplicate requestId: ${message.requestId}`);
      }
      this.requests.set(message.requestId, {
        nextSequence: 1,
        terminal: false,
        method: message.method,
        turnId: message.method === "session.turn" ? String(message.params.turnId) : null,
      });
      return;
    }
    if (message.messageType === "event" && "requestId" in message) {
      const state = this.requests.get(message.requestId);
      if (state === undefined) {
        invalid(`Event references unknown requestId: ${message.requestId}`);
      }
      if (state.terminal) {
        invalid(`Event arrived after terminal result: ${message.requestId}`);
      }
      if (message.sequence !== state.nextSequence) {
        invalid(`Expected sequence ${state.nextSequence}, received ${message.sequence}`);
      }
      state.nextSequence += 1;
      return;
    }
    if (message.messageType === "result") {
      const state = this.requests.get(message.requestId);
      if (state === undefined) {
        invalid(`Result references unknown requestId: ${message.requestId}`);
      }
      if (state.terminal) {
        invalid(`Duplicate terminal result: ${message.requestId}`);
      }
      if (message.ok) {
        validateResultData(state.method, message.data);
        if (state.turnId !== null && message.data.turnId !== state.turnId) {
          invalid("data.turnId must match params.turnId");
        }
      } else if (state.turnId !== null) {
        const details = parseTurnLifecycleDetails(message.error.details);
        if (details.turnId !== state.turnId) {
          invalid("error.details.turnId must match params.turnId");
        }
      }
      state.terminal = true;
    }
  }
}
