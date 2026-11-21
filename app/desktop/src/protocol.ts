import contract from "../protocol/v1/contract.json" with { type: "json" };
import type {
  BibliographyAddDto,
  BibliographyExportDto,
  BibliographyInspectDto,
  BibliographyRenderDto,
} from "./citations.ts";

/**
 * Protocol v1 client helpers.
 *
 * `contract.json` is the only hand-written protocol vocabulary and schema
 * source. Python is the schema validator for every message it sends (U1);
 * this module validates outgoing request params against the contract, parses
 * envelopes, and leaves response correlation to the backend client.
 */

export type JsonObject = Record<string, unknown>;
export type ProtocolOrigin = "python" | "rust";

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

interface ProtocolContract {
  protocolVersion: number;
  requestIdMaxBytes: number;
  errorMessageMaxBytes: number;
  requestEvents: string[];
  processEvents: string[];
  errorCodes: string[];
  methods: { name: string; params: FieldSchema }[];
  resultDataSchemas: Record<string, FieldSchema>;
  submittedContextSchema: FieldSchema;
  turnErrorDetailsSchema: FieldSchema;
}

// The JSON module type widens field-rule `type` values to string.
const CONTRACT = contract as unknown as ProtocolContract;

export const PROTOCOL_VERSION: number = CONTRACT.protocolVersion;
export const MAX_REQUEST_ID_BYTES: number = CONTRACT.requestIdMaxBytes;
export const MAX_ERROR_MESSAGE_BYTES: number = CONTRACT.errorMessageMaxBytes;
export const PROTOCOL_METHODS: readonly string[] = CONTRACT.methods.map(({ name }) => name);
export const REQUEST_EVENTS: readonly string[] = CONTRACT.requestEvents;
export const PROCESS_EVENTS: readonly string[] = CONTRACT.processEvents;
export const PROTOCOL_ERROR_CODES: readonly string[] = CONTRACT.errorCodes;

const METHOD_PARAMS: ReadonlyMap<string, FieldSchema> = new Map(
  CONTRACT.methods.map(({ name, params }) => [name, params]),
);

/** Logical identifiers a result echoes from its request. */
const ECHO_ID_FIELDS = ["projectId", "sessionId", "turnId"] as const;

/**
 * Identifier fields both the method's params and its result schema declare,
 * derived from the contract. Callers compare them only when the request
 * actually carried the field and the result returned it.
 */
export function echoedIdFields(method: ProtocolMethod): readonly string[] {
  const params = METHOD_PARAMS.get(method) ?? {};
  const result = CONTRACT.resultDataSchemas[method] ?? {};
  return ECHO_ID_FIELDS.filter((field) => field in params && field in result);
}

/**
 * Methods without a result DTO in `MethodResults`. `tests/protocol_types.test.ts`
 * keeps `ProtocolMethod` equal to the contract method list.
 */
export type MethodWithoutResultDto =
  | "session.set_thinking";

/** Every contract method: those with a result DTO plus those without one. */
export type ProtocolMethod = keyof MethodResults | MethodWithoutResultDto;

/** Request events without a data DTO in `EventData`. */
export type RequestEventWithoutDataDto =
  | "request.started"
  | "stage.changed"
  | "tool.started"
  | "tool.finished"
  | "tool.failed";

/** Every contract request event; checked against the contract by `tests/protocol_types.test.ts`. */
export type RequestEvent = keyof EventData | RequestEventWithoutDataDto;

/** Process event names; checked against the contract by `tests/protocol_types.test.ts`. */
export type ProcessEvent =
  | "backend.ready"
  | "backend.crashed"
  | "backend.shutting_down"
  | "backend.protocol_error";


export interface ProtocolErrorDto {
  code: string;
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
  registrationStatus?: "registered" | "pending" | "not_required";
  registrationIssue?: string | null;
  extensionAction?: "status" | "preview";
}

export type PermissionMode = "ask" | "bypass";

export interface SessionCreatedDto {
  sessionId: string;
  turnCount: number;
  graphRecursionLimit: number;
  thinkingMode: "normal" | "extended";
  permissionMode: PermissionMode;
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

export interface SessionDeletedDto {
  projectId: string;
  sessionId: string;
  status: "deleted";
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

export interface DocumentOpenDto {
  path: string;
  sourceText: string;
  diskFingerprint: string;
  rootPath?: string;
  editorRevision?: number;
}

/** Result of `document.save` and `document.apply`. */
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

export interface RuntimeShutdownDto {
  status: "stopped" | "no_session";
}

export interface BibliographySetStyleDto {
  styleId: string;
  researchFingerprint: string;
}

export interface BibliographyRemoveDto {
  key: string;
  libraryFingerprint: string;
}

export interface TurnAcceptedDto {
  sessionId: string;
  turnId: string;
}

export interface DocumentProposedDto {
  turnId: string;
  callId: string;
  referenceId?: string;
}

export interface ApprovalRequiredDto {
  approvalId: string;
  parentRequestId: string;
  turnId: string;
  command?: string;
  operation?: "document.apply" | "document.undo" | "citation.save" | "knowledge.init_workspace" | "knowledge.ingest_file" | "knowledge.ingest_folder" | "knowledge.prune_apply" | "mcp.call" | "extension.install";
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

export interface SessionPermissionSetDto {
  sessionId: string;
  permissionMode: PermissionMode;
}

/**
 * Result DTO for every method with a contract `resultDataSchemas` entry. The
 * DTOs are hand-written types; `tests/protocol_types.test.ts` fails when one
 * drifts from its schema.
 */
export interface MethodResults {
  "runtime.diagnostics": RuntimeDiagnosticsDto;
  "runtime.shutdown": RuntimeShutdownDto;
  "project.list": ProjectListDto;
  "workspace.select": ProjectWorkspaceDto;
  "document.open": DocumentOpenDto;
  "document.save": DocumentResultDto;
  "document.apply": DocumentResultDto;
  "session.create": SessionCreatedDto;
  "session.list": SessionListDto;
  "session.select": SessionSelectedDto;
  "session.delete": SessionDeletedDto;
  "session.rename": SessionRenamedDto;
  "session.retry_registration": RegistrationRetryDto;
  "session.transcript": SessionTranscriptDto;
  "session.turn": TurnCompletedDto;
  "session.set_permission": SessionPermissionSetDto;
  "session.stop": TurnStoppedDto;
  "extensions.preview": ExtensionPreviewDto;
  "extensions.apply": ExtensionApplyDto;
  "approval.resolve": ApprovalResolvedDto;
  "bibliography.inspect": BibliographyInspectDto;
  "bibliography.render": BibliographyRenderDto;
  "bibliography.set_style": BibliographySetStyleDto;
  "bibliography.remove": BibliographyRemoveDto;
  "bibliography.add": BibliographyAddDto;
  "bibliography.export": BibliographyExportDto;
}

/** Data DTO for every request event with a contract `eventDataSchemas` entry. */
export interface EventData {
  "turn.accepted": TurnAcceptedDto;
  "document.proposed": DocumentProposedDto;
  "approval.required": ApprovalRequiredDto;
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
  validateObjectSchema(details, CONTRACT.turnErrorDetailsSchema, "error.details");
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
  validateObjectSchema(context, CONTRACT.submittedContextSchema, "submittedContext");
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
  validateObjectSchema(params, METHOD_PARAMS.get(method) ?? {}, "params");
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

function parseRequest(message: JsonObject): RequestEnvelope {
  expectExactKeys(
    message,
    ["protocolVersion", "messageType", "requestId", "method", "params"],
    "request",
  );
  const requestId = expectRequestId(message.requestId);
  const method = expectString(message.method, "method");
  if (!includesValue(PROTOCOL_METHODS as readonly ProtocolMethod[], method)) {
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

function parseEvent(message: JsonObject): EventEnvelope {
  const event = expectString(message.event, "event");
  const data = expectObject(message.data, "data");
  if (message.requestId === undefined) {
    expectExactKeys(message, ["protocolVersion", "messageType", "event", "data"], "event");
    if (message.sequence !== undefined) {
      invalid("Process events cannot carry a sequence");
    }
    if (!includesValue(PROCESS_EVENTS as readonly ProcessEvent[], event)) {
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
  if (!includesValue(REQUEST_EVENTS as readonly RequestEvent[], event)) {
    invalid(`Unknown request event: ${event}`);
  }
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
  if (!PROTOCOL_ERROR_CODES.includes(code)) {
    invalid(`Unknown error code: ${code}`);
  }
  if (typeof error.retryable !== "boolean") {
    invalid("error.retryable must be a boolean");
  }
  const message = expectString(error.message, "error.message");
  if (encoder.encode(message).byteLength > MAX_ERROR_MESSAGE_BYTES) {
    invalid("error.message is too large");
  }
  return {
    code,
    message,
    retryable: error.retryable,
    details: expectObject(error.details, "error.details"),
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
    return {
      protocolVersion: PROTOCOL_VERSION,
      messageType: "result",
      requestId,
      ok: true,
      data: expectObject(message.data, "data"),
    };
  }
  if (message.ok === false) {
    expectExactKeys(
      message,
      ["protocolVersion", "messageType", "requestId", "ok", "error"],
      "result",
    );
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

/** Parse one protocol envelope; request params are validated against the contract. */
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

export interface ProjectWorkspaceDto {
  rootPath: string;
  projectId: string;
  historyDirectory: string;
  rulesText: string;
  rulesFingerprint: string;
  researchFingerprint: string | null;
  status: "ready" | "needs_configuration" | "needs_initialization" | "opened";
}
