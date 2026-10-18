export const PROTOCOL_VERSION = 1 as const;
export const MAX_PROTOCOL_LINE_BYTES = 2 * 1024 * 1024;
export const MAX_REQUEST_ID_BYTES = 128;
export const MAX_ERROR_MESSAGE_BYTES = 4096;
export const FULL_TEXT_RESULT_METHODS = ["session.turn", "session.transcript"] as const;

export const PROTOCOL_METHODS = [
  "runtime.diagnostics",
  "project.list",
  "workspace.select",
  "document.open",
  "document.save",
  "document.apply",
  "session.create",
  "session.list",
  "session.select",
  "session.rename",
  "session.retry_registration",
  "session.transcript",
  "session.status",
  "session.turn",
  "session.set_thinking",
  "session.set_bash_permission",
  "session.stop",
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
  "turn.accepted",
  "request.progress",
  "stage.changed",
  "tool.started",
  "tool.finished",
  "tool.failed",
  "document.proposed",
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
  "TURN_CANCELLED",
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
    | "object"
    | "objectArray"
    | "submittedContext"
    | "nullableSubmittedContext"
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
  allowEmpty?: boolean;
  pattern?: string;
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

export const DOCUMENT_CONTEXT_SCHEMA: FieldSchema = {
  rootPath: { type: "string", required: true, maxBytes: 8192 },
  path: { type: "string", required: true, maxBytes: 8192 },
  editorRevision: { type: "integer", required: true, minimum: 0, maximum: 9007199254740991 },
  sourceText: { type: "string", required: true, maxBytes: 1048576, allowEmpty: true },
  diskFingerprint: { type: "string", required: true, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
  rangeStartUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  rangeEndUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
};

export const SUBMITTED_CONTEXT_SCHEMA: FieldSchema = {
  "projectId": {
    "type": "string",
    "required": true,
    "maxBytes": 64,
    "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"
  },
  "rootPath": {
    "type": "string",
    "required": true,
    "maxBytes": 8192
  },
  "permissionMode": {
    "type": "string",
    "required": true,
    "enum": [
      "ask",
      "bypass"
    ]
  },
  "requestedThinkingMode": {
    "type": "string",
    "required": true,
    "enum": [
      "normal",
      "extended"
    ]
  },
  "skillReferences": {
    "type": "objectArray",
    "required": true,
    "maxItems": 128,
    "items": {
      "name": {
        "type": "string",
        "required": true,
        "maxBytes": 256
      },
      "startUtf16": {
        "type": "integer",
        "required": true,
        "minimum": 0,
        "maximum": 9007199254740991
      },
      "endUtf16": {
        "type": "integer",
        "required": true,
        "minimum": 0,
        "maximum": 9007199254740991
      }
    }
  },
  "projectRules": {
    "type": "object",
    "required": true,
    "items": {
      "text": {
        "type": "string",
        "required": true,
        "maxBytes": 1048576,
        "allowEmpty": true
      },
      "fingerprint": {
        "type": "string",
        "required": true,
        "maxBytes": 64,
        "pattern": "^[0-9a-f]{64}$"
      }
    }
  },
  "documentContext": {
    "type": "object",
    "required": false,
    "items": {
      "rootPath": {
        "type": "string",
        "required": true,
        "maxBytes": 8192
      },
      "path": {
        "type": "string",
        "required": true,
        "maxBytes": 8192
      },
      "editorRevision": {
        "type": "integer",
        "required": true,
        "minimum": 0,
        "maximum": 9007199254740991
      },
      "sourceText": {
        "type": "string",
        "required": true,
        "maxBytes": 1048576,
        "allowEmpty": true
      },
      "diskFingerprint": {
        "type": "string",
        "required": true,
        "maxBytes": 64,
        "pattern": "^[0-9a-f]{64}$"
      },
      "rangeStartUtf16": {
        "type": "integer",
        "required": false,
        "minimum": 0,
        "maximum": 9007199254740991
      },
      "rangeEndUtf16": {
        "type": "integer",
        "required": false,
        "minimum": 0,
        "maximum": 9007199254740991
      }
    }
  },
  "references": {
    "type": "objectArray",
    "required": true,
    "items": {
      "referenceId": {
        "type": "string",
        "required": true,
        "maxBytes": 256
      },
      "kind": {
        "type": "string",
        "required": true,
        "enum": [
          "document",
          "chat"
        ]
      },
      "text": {
        "type": "string",
        "required": true,
        "maxBytes": 1048576,
        "allowEmpty": false
      },
      "document": {
        "type": "object",
        "required": false,
        "items": {
          "snapshot": {
            "type": "object",
            "required": true,
            "items": {
              "rootPath": {
                "type": "string",
                "required": true,
                "maxBytes": 8192
              },
              "path": {
                "type": "string",
                "required": true,
                "maxBytes": 8192
              },
              "editorRevision": {
                "type": "integer",
                "required": true,
                "minimum": 0,
                "maximum": 9007199254740991
              },
              "sourceText": {
                "type": "string",
                "required": true,
                "maxBytes": 1048576,
                "allowEmpty": true
              },
              "diskFingerprint": {
                "type": "string",
                "required": true,
                "maxBytes": 64,
                "pattern": "^[0-9a-f]{64}$"
              },
              "rangeStartUtf16": {
                "type": "integer",
                "required": true,
                "minimum": 0,
                "maximum": 9007199254740991
              },
              "rangeEndUtf16": {
                "type": "integer",
                "required": true,
                "minimum": 0,
                "maximum": 9007199254740991
              }
            }
          },
          "startLine": {
            "type": "integer",
            "required": true,
            "minimum": 1,
            "maximum": 9007199254740991
          },
          "endLine": {
            "type": "integer",
            "required": true,
            "minimum": 1,
            "maximum": 9007199254740991
          }
        }
      },
      "chat": {
        "type": "object",
        "required": false,
        "items": {
          "projectId": {
            "type": "string",
            "required": true,
            "maxBytes": 64,
            "pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"
          },
          "sessionId": {
            "type": "turnId",
            "required": true
          },
          "turnId": {
            "type": "turnId",
            "required": true
          },
          "role": {
            "type": "string",
            "required": true,
            "enum": [
              "user",
              "assistant"
            ]
          },
          "messageFingerprint": {
            "type": "string",
            "required": true,
            "maxBytes": 64,
            "pattern": "^[0-9a-f]{64}$"
          },
          "startUtf16": {
            "type": "integer",
            "required": true,
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "endUtf16": {
            "type": "integer",
            "required": true,
            "minimum": 0,
            "maximum": 9007199254740991
          }
        }
      }
    }
  }
};

export const DOCUMENT_APPROVAL_DATA_SCHEMA: FieldSchema = {
  approvalId: { type: "string", required: true, maxBytes: 256 },
  parentRequestId: { type: "requestId", required: true },
  turnId: { type: "string", required: true, maxBytes: 256 },
  operation: { type: "string", required: true, enum: ["document.apply", "document.undo", "citation.save", "knowledge.init_workspace", "knowledge.ingest_file", "knowledge.ingest_folder", "knowledge.prune_apply", "mcp.call", "extension.install", "extensions.apply"] },
  targetPath: { type: "string", required: true, maxBytes: 8192 },
  rangeStartUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  rangeEndUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  parametersSummary: { type: "string", required: false, maxBytes: 8192 },
  description: { type: "string", required: true, maxBytes: 4096 },
  createdAt: { type: "utcTimestamp", required: true },
  expiresAt: { type: "utcTimestamp", required: true },
};

export const DOCUMENT_RESULT_SCHEMA: FieldSchema = {
  path: { type: "string", required: true, maxBytes: 8192 },
  status: { type: "string", required: true, enum: ["saved", "conflict", "failed", "cancelled"] },
  sourceText: { type: "string", required: false, maxBytes: 1048576, allowEmpty: true },
  diskFingerprint: { type: "string", required: false, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
  rangeStartUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  rangeEndUtf16: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  candidateText: { type: "string", required: false, maxBytes: 1048576, allowEmpty: true },
  currentDiskText: { type: "string", required: false, maxBytes: 1048576, allowEmpty: true },
  issue: { type: "string", required: false, maxBytes: 4096 },
  callId: { type: "string", required: false, maxBytes: 256 },
  rootPath: { type: "string", required: false, maxBytes: 8192 },
  editorRevision: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  savedFingerprint: { type: "string", required: false, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
  expectedSnapshot: { type: "object", required: false, items: DOCUMENT_CONTEXT_SCHEMA },
};

export const EVENT_DATA_SCHEMAS: Partial<Record<RequestEvent, FieldSchema>> = {
  "turn.accepted": {
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnId: { type: "turnId", required: true },
  },
  "document.proposed": {
    turnId: { type: "turnId", required: true },
    callId: { type: "string", required: true, maxBytes: 256 },
    referenceId: { type: "string", required: false, maxBytes: 256, pattern: "^[\\s\\S]*\\S[\\s\\S]*$" },
  },
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
  "workspace.select": {
    rootPath: { type: "string", required: true, maxBytes: 8192 },
    projectId: { type: "string", required: true, maxBytes: 256 },
    historyDirectory: { type: "string", required: true, maxBytes: 8192 },
    rulesText: { type: "string", required: true, maxBytes: 1048576, allowEmpty: true },
    rulesFingerprint: { type: "string", required: true, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
    researchFingerprint: { type: "nullableString", required: true, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
    status: { type: "string", required: true, enum: ["ready", "needs_configuration", "needs_initialization", "opened"] },
  },
  "document.open": {
    path: { type: "string", required: true, maxBytes: 8192 },
    sourceText: { type: "string", required: true, maxBytes: 1048576, allowEmpty: true },
    diskFingerprint: { type: "string", required: true, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
    rootPath: { type: "string", required: false, maxBytes: 8192 },
    editorRevision: { type: "integer", required: false, minimum: 0, maximum: 9007199254740991 },
  },
  "document.save": DOCUMENT_RESULT_SCHEMA,
  "document.apply": DOCUMENT_RESULT_SCHEMA,
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
    thinkingMode: { type: "string", required: true, enum: ["normal", "extended"] },
    bashPermissionMode: { type: "string", required: true, enum: ["ask", "bypass"] },
    slashCommands: {
      type: "objectArray", required: true, maxItems: 512,
      items: {
        name: { type: "string", required: true, maxBytes: 64 },
        description: { type: "string", required: true, maxBytes: 1_024 },
      },
    },
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
    documentOperations: {
      type: "objectArray",
      required: false,
      maxItems: 128,
      items: {
        callId: { type: "string", required: true, maxBytes: 256 },
        path: { type: "string", required: true, maxBytes: 8192 },
        candidateText: { type: "string", required: true, maxBytes: 1048576, allowEmpty: true },
        rangeStartUtf16: { type: "integer", required: true, minimum: 0, maximum: 9007199254740991 },
        rangeEndUtf16: { type: "integer", required: true, minimum: 0, maximum: 9007199254740991 },
      },
    },
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnId: { type: "turnId", required: true },
    turnNumber: { type: "integer", required: true, minimum: 1, maximum: 4_096 },
    state: { type: "string", required: true, enum: ["completed"] },
    accepted: { type: "boolean", required: true },
    persisted: { type: "boolean", required: true },
    text: { type: "string", required: true },
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
  "session.stop": {
    sessionId: { type: "string", required: true, maxBytes: 32 },
    turnId: { type: "turnId", required: true },
    state: { type: "nullableString", required: true, enum: ["completed", "failed", "interrupted"] },
    accepted: { type: "boolean", required: true },
    persisted: { type: "boolean", required: true },
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
    thinkingMode: { type: "string", required: true, enum: ["normal", "extended"] },
    bashPermissionMode: { type: "string", required: true, enum: ["ask", "bypass"] },
    slashCommands: {
      type: "objectArray", required: true, maxItems: 512,
      items: {
        name: { type: "string", required: true, maxBytes: 64 },
        description: { type: "string", required: true, maxBytes: 1_024 },
      },
    },
    loadedSkills: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 256 },
    mcpFamilies: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 256 },
    startupDiagnostics: { type: "stringArray", required: true, maxItems: 512, itemMaxBytes: 4_096 },
    extensionRevision: { type: "integer", required: true, minimum: 0, maximum: 0xffff_ffff },
    projectId: { type: "string", required: true, maxBytes: 256 },
    registered: { type: "boolean", required: true },
  },
  "session.rename": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
    title: { type: "string", required: true, maxBytes: 256 },
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
        userText: { type: "string", required: true },
        submittedContext: { type: "nullableSubmittedContext", required: false },
        assistantText: { type: "nullableString", required: true },
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
    sessionId: { type: "string", required: true, maxBytes: 256 },
    turnId: { type: "turnId", required: true },
    turnNumber: { type: "integer", required: true, minimum: 1, maximum: 4_096 },
    state: { type: "string", required: true, enum: ["completed"] },
    accepted: { type: "boolean", required: true },
    persisted: { type: "boolean", required: true },
    text: { type: "string", required: true, maxBytes: 65_536 },
    displayInput: { type: "string", required: true, maxBytes: 256 },
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
  "session.set_bash_permission": {
    sessionId: { type: "string", required: true, maxBytes: 256 },
    bashPermissionMode: { type: "string", required: true, enum: ["ask", "bypass"] },
  },
};

export const METHOD_PARAM_SCHEMAS: Record<ProtocolMethod, FieldSchema> = {
  "workspace.select": {
    rootPath: { type: "string", required: true, maxBytes: 8192 },
    action: { type: "string", required: false, enum: ["inspect", "open", "initialize"] },
    historyDirectory: { type: "string", required: false, maxBytes: 8192 },
    expectedFingerprint: { type: "nullableString", required: false, maxBytes: 64, pattern: "^[0-9a-f]{64}$" },
  },
  "document.open": {
    path: { type: "string", required: true, maxBytes: 8192 },
  },
  "document.save": {
    documentContext: { type: "object", required: true, items: DOCUMENT_CONTEXT_SCHEMA },
  },
  "document.apply": {
    documentContext: { type: "object", required: true, items: DOCUMENT_CONTEXT_SCHEMA },
    turnId: { type: "turnId", required: true },
    callId: { type: "string", required: false, maxBytes: 256 },
    parentRequestId: { type: "requestId", required: false },
    undoOfCallId: { type: "string", required: false, maxBytes: 256 },
    resolution: { type: "string", required: false, enum: ["keep", "use", "cancel"] },
    expectedSnapshot: { type: "object", required: false, items: DOCUMENT_CONTEXT_SCHEMA },
  },
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
    reconcile: { type: "boolean", required: false },
  },
  "session.select": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
  },
  "session.rename": {
    projectId: { type: "string", required: true, maxBytes: 256 },
    sessionId: { type: "string", required: true, maxBytes: 32 },
    title: { type: "string", required: true, maxBytes: 256 },
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
    submittedContext: { type: "submittedContext", required: false },
    skillReferences: {
      type: "objectArray",
      required: false,
      maxItems: 128,
      items: {
        name: { type: "string", required: true, maxBytes: 256 },
        startUtf16: { type: "integer", required: true, minimum: 0, maximum: 9007199254740991 },
        endUtf16: { type: "integer", required: true, minimum: 0, maximum: 9007199254740991 },
      },
    },
    documentContext: { type: "object", required: false, items: DOCUMENT_CONTEXT_SCHEMA },
    text: { type: "string", required: true, maxBytes: 1_048_576 },
    turnId: { type: "turnId", required: true },
    retry: { type: "boolean", required: true },
  },
  "session.set_thinking": {
    mode: { type: "string", required: true, enum: ["normal", "extended"] },
  },
  "session.set_bash_permission": {
    mode: { type: "string", required: true, enum: ["ask", "bypass"] },
  },
  "session.stop": {
    sessionId: { type: "string", required: true, maxBytes: 32 },
    turnId: { type: "turnId", required: true },
    parentRequestId: { type: "requestId", required: true },
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
    turnId: { type: "turnId", required: true },
    retry: { type: "boolean", required: true },
  },
  "approval.resolve": {
    documentContext: { type: "object", required: false, items: DOCUMENT_CONTEXT_SCHEMA },
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

export interface TurnStoppedDto {
  sessionId: string;
  turnId: string;
  state: "completed" | "failed" | "interrupted" | null;
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
  documentOperations?: DocumentOperationDto[];
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

export type BashPermissionMode = "ask" | "bypass";

export interface SessionCreatedDto {
  sessionId: string;
  turnCount: number;
  graphRecursionLimit: number;
  thinkingMode: "normal" | "extended";
  bashPermissionMode: BashPermissionMode;
  slashCommands: { name: string; description: string }[];
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

export interface SessionRenamedDto {
  projectId: string;
  sessionId: string;
  title: string;
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
  submittedContext?: SubmittedContext | null;
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
  sessionId: string;
  turnId: string;
  turnNumber: number;
  state: "completed";
  accepted: boolean;
  persisted: boolean;
  text: string;
  displayInput: string;
  previousRevision: number;
  appliedRevision: number;
  restartRequired: boolean;
  items: ExtensionApplyItemDto[];
  diagnostics: string[];
}

export interface SkillReferenceDto {
  name: string;
  startUtf16: number;
  endUtf16: number;
}

export interface DocumentContextDto {
  rootPath: string;
  path: string;
  editorRevision: number;
  sourceText: string;
  diskFingerprint: string;
  rangeStartUtf16?: number;
  rangeEndUtf16?: number;
}

export type Reference =
  | {
      referenceId: string;
      kind: "document";
      text: string;
      document: {
        snapshot: DocumentContextDto & { rangeStartUtf16: number; rangeEndUtf16: number };
        startLine: number;
        endLine: number;
      };
    }
  | {
      referenceId: string;
      kind: "chat";
      text: string;
      chat: {
        projectId: string;
        sessionId: string;
        turnId: string;
        role: "user" | "assistant";
        messageFingerprint: string;
        startUtf16: number;
        endUtf16: number;
      };
    };

export interface SubmittedContext {
  projectId: string;
  rootPath: string;
  permissionMode: "ask" | "bypass";
  requestedThinkingMode: "normal" | "extended";
  skillReferences: SkillReferenceDto[];
  projectRules: { text: string; fingerprint: string };
  documentContext?: DocumentContextDto;
  references: Reference[];
}

export interface DocumentOperationDto {
  callId: string;
  path: string;
  candidateText: string;
  rangeStartUtf16: number;
  rangeEndUtf16: number;
}

export interface DocumentOpenDto {
  path: string;
  sourceText: string;
  diskFingerprint: string;
  rootPath?: string;
  editorRevision?: number;
}

export interface DocumentResultDto {
  path: string;
  status: "saved" | "conflict" | "failed" | "cancelled";
  sourceText?: string;
  diskFingerprint?: string;
  savedFingerprint?: string;
  rootPath?: string;
  editorRevision?: number;
  expectedSnapshot?: DocumentContextDto;
  rangeStartUtf16?: number;
  rangeEndUtf16?: number;
  candidateText?: string;
  currentDiskText?: string;
  issue?: string;
  callId?: string;
}

export interface ApprovalRequiredDto {
  approvalId: string;
  parentRequestId: string;
  turnId: string;
  command?: string;
  operation?: "document.apply" | "document.undo" | "citation.save" | "knowledge.init_workspace" | "knowledge.ingest_file" | "knowledge.ingest_folder" | "knowledge.prune_apply" | "mcp.call" | "extension.install" | "extensions.apply";
  targetPath?: string;
  rangeStartUtf16?: number;
  rangeEndUtf16?: number;
  parametersSummary?: string;
  description: string;
  executionTimeoutSeconds?: number;
  createdAt: string;
  expiresAt: string;
}

export interface ApprovalResolvedDto {
  approvalId: string;
  approved: boolean;
}

export interface SessionBashPermissionSetDto {
  sessionId: string;
  bashPermissionMode: BashPermissionMode;
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
  if (rule.type === "submittedContext" || rule.type === "nullableSubmittedContext") {
    if (value === null && rule.type === "nullableSubmittedContext") return;
    validateSubmittedContext(value);
    return;
  }
  if (rule.type === "string") {
    const text = rule.allowEmpty && typeof value === "string" ? value : expectString(value, field);
    if (rule.pattern !== undefined) {
      const match = new RegExp(rule.pattern).exec(text);
      if (!match || match.index !== 0 || match[0].length !== text.length) invalid(`${field} has an invalid format`);
    }
    for (let index = 0; index < text.length; index += 1) {
      const unit = text.charCodeAt(index);
      if (unit >= 0xd800 && unit <= 0xdbff) {
        const next = text.charCodeAt(++index);
        if (!(next >= 0xdc00 && next <= 0xdfff)) invalid(`${field} must contain valid Unicode`);
      } else if (unit >= 0xdc00 && unit <= 0xdfff) {
        invalid(`${field} must contain valid Unicode`);
      }
    }
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
  if (rule.type === "object") {
    validateObjectSchema(expectObject(value, field), rule.items!, field);
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

function validateDocumentRange(value: JsonObject, field: string, source = false): void {
  const start = value.rangeStartUtf16 as number | undefined;
  const end = value.rangeEndUtf16 as number | undefined;
  if ((start === undefined) !== (end === undefined)) invalid(`${field} requires both UTF-16 range endpoints`);
  if (start === undefined || end === undefined) return;
  if (start > end) invalid(`${field} has a reversed UTF-16 range`);
  if (source) {
    const text = value.sourceText as string;
    for (const offset of [start, end]) {
      if (offset > text.length) invalid(`${field} range exceeds source text`);
      const unit = text.charCodeAt(offset);
      if (unit >= 0xdc00 && unit <= 0xdfff) invalid(`${field} range splits a surrogate pair`);
    }
  }
}

function validateSkillReferences(params: JsonObject): void {
  const text = params.text as string;
  for (const item of (params.skillReferences ?? []) as SkillReferenceDto[]) {
    const start = item.startUtf16;
    const end = item.endUtf16;
    if (start > end || end > text.length) invalid("params.skillReferences has an invalid UTF-16 range");
    for (const offset of [start, end]) {
      const unit = text.charCodeAt(offset);
      if (unit >= 0xdc00 && unit <= 0xdfff) invalid("params.skillReferences range splits a surrogate pair");
    }
    if (text.slice(start, end) !== "@" + item.name) invalid("params.skillReferences does not match the original text");
    if (start > 0 && /[A-Za-z0-9_.@+-]/.test(text[start - 1])) {
      invalid("params.skillReferences must begin at a Skill token boundary");
    }
    if (/^[A-Za-z0-9_-]|^\.[A-Za-z0-9]/.test(text.slice(end))) {
      invalid("params.skillReferences must end at a Skill token boundary");
    }
  }
}

function validateProjectPath(value: string, field: string): void {
  if (!value.startsWith("/") || /[\\\x00-\x1f\x7f]/.test(value) ||
      (value !== "/" && value.split("/").slice(1).some((part) => !part || part === "." || part === ".."))) {
    invalid(`${field} must be an absolute normalized Linux path`);
  }
}

function validateContextDocument(snapshot: DocumentContextDto, root: string): void {
  validateProjectPath(snapshot.path, "document.path");
  if (snapshot.rootPath !== root || snapshot.path === root ||
      !snapshot.path.startsWith(root === "/" ? "/" : root + "/")) {
    invalid("document snapshot belongs to another project root");
  }
  validateDocumentRange(snapshot as unknown as JsonObject, "submittedContext.document", true);
}

export function validateSubmittedContext(value: unknown): asserts value is SubmittedContext {
  const context = expectObject(value, "submittedContext");
  validateObjectSchema(context, SUBMITTED_CONTEXT_SCHEMA, "submittedContext");
  if (encoder.encode(JSON.stringify(context)).byteLength > 1_048_576) invalid("submittedContext exceeds the 1 MiB input limit");
  const submitted = value as SubmittedContext;
  validateProjectPath(submitted.rootPath, "rootPath");
  for (const skill of submitted.skillReferences) {
    if (!skill.name.trim() || skill.endUtf16 <= skill.startUtf16) invalid("invalid submitted Skill reference");
  }
  if (submitted.documentContext) validateContextDocument(submitted.documentContext, submitted.rootPath);
  const seen = new Set<string>();
  for (const reference of submitted.references) {
    if (!reference.referenceId.trim() || seen.has(reference.referenceId)) invalid("referenceId must be nonblank and unique");
    seen.add(reference.referenceId);
    if (reference.kind === "document") {
      if (!("document" in reference) || "chat" in reference) invalid("document reference requires only document source");
      const { snapshot, startLine, endLine } = reference.document;
      validateContextDocument(snapshot, submitted.rootPath);
      const start = snapshot.rangeStartUtf16, end = snapshot.rangeEndUtf16;
      if (snapshot.sourceText.slice(start, end) !== reference.text) invalid("document reference text does not match frozen range");
      const breaks = [...snapshot.sourceText.matchAll(/\r\n|\r|\n/g)].map((match) => match.index! + match[0].length);
      if (startLine !== 1 + breaks.filter((offset) => offset <= start).length ||
          endLine !== 1 + breaks.filter((offset) => offset < end).length) {
        invalid("document reference line numbers do not match frozen range");
      }
    } else {
      if (!("chat" in reference) || "document" in reference) invalid("chat reference requires only chat source");
      const chat = reference.chat;
      if (chat.projectId !== submitted.projectId || chat.endUtf16 <= chat.startUtf16 ||
          chat.endUtf16 - chat.startUtf16 !== reference.text.length) {
        invalid("chat reference project or UTF-16 range is invalid");
      }
    }
  }
}

function validateSubmissionSize(text: string, submittedContext: SubmittedContext): void {
  if (encoder.encode(JSON.stringify({ text, submittedContext })).byteLength > 1_048_576) {
    invalid("text and submittedContext exceed the 1 MiB input limit");
  }
}

function validateParams(method: ProtocolMethod, params: JsonObject): void {
  validateObjectSchema(params, METHOD_PARAM_SCHEMAS[method], "params");
  if (method === "session.turn") {
    validateSkillReferences(params);
    if (params.submittedContext !== undefined) {
      const context = params.submittedContext as SubmittedContext;
      validateSkillReferences({ text: params.text, skillReferences: context.skillReferences });
      validateSubmissionSize(params.text as string, context);
    }
  }
  if (params.documentContext !== undefined) validateDocumentRange(params.documentContext as JsonObject, "params.documentContext", true);
  if (params.expectedSnapshot !== undefined) validateDocumentRange(params.expectedSnapshot as JsonObject, "params.expectedSnapshot", true);
  if (method === "document.apply" && (("callId" in params) === ("undoOfCallId" in params))) {
    invalid("document.apply requires exactly one of callId or undoOfCallId");
  }
}

export function validateResultData(method: ProtocolMethod, data: JsonObject): void {
  validateSafeData(data, "data");
  const schema = RESULT_DATA_SCHEMAS[method];
  if (schema !== undefined) {
    validateObjectSchema(data, schema, "data");
  }
  if (method === "document.save" || method === "document.apply") {
    validateDocumentRange(data, "data");
    if (data.expectedSnapshot !== undefined) validateDocumentRange(data.expectedSnapshot as JsonObject, "data.expectedSnapshot", true);
  }
  if (method === "session.turn" && data.documentOperations !== undefined) {
    (data.documentOperations as JsonObject[]).forEach((item) => validateDocumentRange(item, "data.documentOperations"));
  }
  if (
    (method === "session.turn" || method === "extensions.apply") &&
    (data.state !== "completed" || data.accepted !== true || data.persisted !== true)
  ) {
    invalid(`${method} success must be durably completed`);
  }
  if (method === "session.stop") {
    const durable = data.state !== null;
    if (data.accepted !== durable || data.persisted !== durable) {
      invalid("session.stop lifecycle must match its durable state");
    }
  }
  if (method === "session.transcript") {
    (data.items as JsonObject[]).forEach((item) => {
      const context = item.submittedContext as SubmittedContext | null | undefined;
      if (context) {
        if (context.projectId !== data.projectId) invalid("transcript submittedContext belongs to another project");
        validateSkillReferences({ text: item.userText, skillReferences: context.skillReferences });
        validateSubmissionSize(item.userText as string, context);
      }
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
  const schema = event === "approval.required" && "operation" in data
    ? DOCUMENT_APPROVAL_DATA_SCHEMA : EVENT_DATA_SCHEMAS[event];
  if (schema !== undefined) {
    validateObjectSchema(data, schema, "data");
  }
  if (event === "approval.required" && "operation" in data) validateDocumentRange(data, "data");
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
  sessionId: string | null;
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
        turnId:
          message.method === "session.turn" || message.method === "extensions.apply" || message.method === "session.stop"
            ? String(message.params.turnId)
            : null,
        sessionId: message.method === "session.stop" ? String(message.params.sessionId) : null,
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
      if ((message.event === "document.proposed" || message.event === "turn.accepted") &&
          (state.method !== "session.turn" || message.data.turnId !== state.turnId)) {
        invalid(`${message.event} must match the active session.turn`);
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
        if (state.method === "session.stop" && message.data.sessionId !== state.sessionId) {
          invalid("data.sessionId must match params.sessionId");
        }
      } else if (state.method === "session.turn" || state.method === "extensions.apply") {
        const details = parseTurnLifecycleDetails(message.error.details);
        if (details.turnId !== state.turnId) {
          invalid("error.details.turnId must match params.turnId");
        }
      }
      state.terminal = true;
    }
  }
}

export interface ProjectWorkspaceDto {
  rootPath: string;
  projectId: string;
  historyDirectory: string;
  rulesText: string;
  rulesFingerprint: string;
  researchFingerprint: string | null;
  status: "ready" | "needs_configuration" | "needs_initialization" | "opened";
}
