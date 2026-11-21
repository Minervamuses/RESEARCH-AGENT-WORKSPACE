import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  MAX_ERROR_MESSAGE_BYTES,
  MAX_REQUEST_ID_BYTES,
  PROCESS_EVENTS,
  PROTOCOL_ERROR_CODES,
  PROTOCOL_METHODS,
  PROTOCOL_VERSION,
  ProtocolContractError,
  REQUEST_EVENTS,
  echoedIdFields,
  parseProtocolMessage,
} from "../src/protocol.ts";

interface ContractFieldRule {
  type: string;
  required: boolean;
  maxBytes?: number;
  minimum?: number;
  maximum?: number;
  maxItems?: number;
  itemMaxBytes?: number;
  enum?: string[];
  items?: Record<string, ContractFieldRule>;
}

interface ContractMethod {
  name: string;
  operation: string;
  requiredParams: string[];
  params: Record<string, ContractFieldRule>;
}

interface ContractDocument {
  protocolVersion: number;
  requestIdMaxBytes: number;
  errorMessageMaxBytes: number;
  requestEvents: string[];
  processEvents: string[];
  resultDataSchemas: Record<string, Record<string, ContractFieldRule>>;
  methods: ContractMethod[];
  errorCodes: string[];
}

interface MessageFixture {
  name: string;
  valid: boolean;
  errorCode?: string;
  message: unknown;
}

interface FixtureDocument {
  messages: MessageFixture[];
}

const currentDir = dirname(fileURLToPath(import.meta.url));
const protocolDir = resolve(currentDir, "../protocol/v1");

async function loadJson<T>(name: string): Promise<T> {
  return JSON.parse(await readFile(resolve(protocolDir, name), "utf8")) as T;
}

function matchesExpectedError(error: unknown, code: string | undefined): boolean {
  return error instanceof ProtocolContractError && error.code === code;
}

const requestId = "123e4567-e89b-42d3-a456-426614174000";

function isRequestFixture(fixture: MessageFixture): boolean {
  const message = fixture.message;
  return typeof message === "object" && message !== null &&
    (message as Record<string, unknown>).messageType === "request";
}

test("protocol vocabulary constants are read from contract.json, not copied", async () => {
  // Both sides come from the same file; this only guards against literals creeping back.
  const contract = await loadJson<ContractDocument>("contract.json");
  assert.equal(PROTOCOL_VERSION, contract.protocolVersion);
  assert.equal(MAX_REQUEST_ID_BYTES, contract.requestIdMaxBytes);
  assert.equal(MAX_ERROR_MESSAGE_BYTES, contract.errorMessageMaxBytes);
  assert.deepEqual([...PROTOCOL_METHODS], contract.methods.map(({ name }) => name));
  assert.deepEqual([...REQUEST_EVENTS], contract.requestEvents);
  assert.deepEqual([...PROCESS_EVENTS], contract.processEvents);
  assert.deepEqual([...PROTOCOL_ERROR_CODES], contract.errorCodes);
});

test("contract method names are unique and expose no generic escape hatches", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const methodNames = new Set(contract.methods.map(({ name }) => name));
  assert.equal(methodNames.size, contract.methods.length);
  for (const forbidden of [
    "run_slash_command",
    "run_shell",
    "read_arbitrary_file",
    "set_any_config_field",
  ]) {
    assert.equal(methodNames.has(forbidden), false);
  }
  for (const method of contract.methods) {
    if (method.operation === "destructive") {
      assert.ok(method.requiredParams.includes("previewId"), method.name);
    }
  }
});

test("echoed identifier fields are derived from params and result schemas", () => {
  assert.deepEqual(echoedIdFields("session.create"), ["projectId"]);
  assert.deepEqual(echoedIdFields("session.list"), ["projectId"]);
  for (const method of ["session.select", "session.delete", "session.rename", "session.transcript"] as const) {
    assert.deepEqual(echoedIdFields(method), ["projectId", "sessionId"], method);
  }
  assert.deepEqual(echoedIdFields("session.turn"), ["turnId"]);
  assert.deepEqual(echoedIdFields("session.stop"), ["sessionId", "turnId"]);
  assert.deepEqual(echoedIdFields("extensions.apply"), ["turnId"]);
  // The request carries turnId, but the success result does not.
  assert.deepEqual(echoedIdFields("document.apply"), []);
  assert.deepEqual(echoedIdFields("approval.resolve"), []);
});

test("normal answers use only the final terminal result", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const turnResult = contract.resultDataSchemas["session.turn"];
  assert.equal(contract.requestEvents.includes("answer.chunk"), false);
  assert.deepEqual(turnResult.streamKind, {
    type: "string",
    required: false,
    enum: ["final_only"],
  });
  assert.deepEqual(turnResult.chunkCount, {
    type: "integer",
    required: false,
    minimum: 0,
    maximum: 0,
  });
  assert.equal("maxBytes" in turnResult.text, false);
});

test("complete answer and transcript results have no client capacity rejection", () => {
  const answer = 'BEGIN 中文🙂\n"quoted"\\path\n' + "界".repeat(750_000) + "\nEND";
  assert.doesNotThrow(() => parseProtocolMessage({
    protocolVersion: 1,
    messageType: "result",
    requestId,
    ok: true,
    data: {
      sessionId: "session-a",
      turnId: "123e4567e89b42d3a456426614174000",
      turnNumber: 1,
      state: "completed",
      accepted: true,
      persisted: true,
      text: answer,
      validationErrors: [],
      toolSummaries: [],
      responseKind: "answer",
    },
  }));
});

test("session turn carries one canonical logical identity and durable lifecycle", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const turn = contract.methods.find(({ name }) => name === "session.turn")!;
  assert.deepEqual(
    Object.entries(turn.params).filter(([, rule]) => rule.required).map(([field]) => field),
    ["text", "turnId", "retry"],
  );
  assert.deepEqual(turn.params.turnId, { type: "turnId", required: true });
  assert.deepEqual(turn.params.retry, { type: "boolean", required: true });
  const result = contract.resultDataSchemas["session.turn"];
  assert.deepEqual(result.turnNumber, { type: "integer", required: true, minimum: 1, maximum: 4_096 });
  assert.deepEqual(result.state, { type: "string", required: true, enum: ["completed"] });
  assert.deepEqual(result.accepted, { type: "boolean", required: true });
  assert.deepEqual(result.persisted, { type: "boolean", required: true });
});

test("extension apply carries its own canonical durable turn lifecycle", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const apply = contract.methods.find(({ name }) => name === "extensions.apply")!;
  assert.deepEqual(
    Object.entries(apply.params).filter(([, rule]) => rule.required).map(([field]) => field),
    ["previewId", "approvedBindingHashes", "turnId", "retry"],
  );
  assert.deepEqual(apply.params.turnId, { type: "turnId", required: true });
  assert.deepEqual(apply.params.retry, { type: "boolean", required: true });
  const result = contract.resultDataSchemas["extensions.apply"];
  assert.deepEqual(result.turnId, { type: "turnId", required: true });
  assert.deepEqual(result.turnNumber, { type: "integer", required: true, minimum: 1, maximum: 4_096 });
  assert.deepEqual(result.state, { type: "string", required: true, enum: ["completed"] });
  assert.deepEqual(result.accepted, { type: "boolean", required: true });
  assert.deepEqual(result.persisted, { type: "boolean", required: true });
});

test("session summaries and transcripts expose canonical lifecycle state", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const summary = contract.resultDataSchemas["session.list"]?.items.items;
  assert.deepEqual(summary?.createdAt, { type: "nullableString", required: true, maxBytes: 64 });

  const turn = contract.resultDataSchemas["session.transcript"]?.items.items;
  assert.deepEqual(Object.keys(turn ?? {}).sort(), [
    "turnId",
    "turnNumber",
    "kind",
    "state",
    "timestamp",
    "userText",
    "submittedContext",
    "assistantText",
    "failureCode",
    "failureMessage",
    "failureRetryable",
    "toolActivities",
  ].sort());
  assert.deepEqual(turn?.turnId, { type: "turnId", required: true });
  assert.deepEqual(turn?.kind, { type: "string", required: true, enum: ["conversational", "display-only"] });
  assert.deepEqual(turn?.state, {
    type: "string",
    required: true,
    enum: ["pending", "completed", "failed", "interrupted"],
  });
  assert.deepEqual(turn?.timestamp, { type: "utcTimestamp", required: true });
  assert.deepEqual(turn?.assistantText, { type: "nullableString", required: true });
  assert.deepEqual(turn?.userText, { type: "string", required: true });
  assert.deepEqual(turn?.failureCode, {
    type: "nullableString",
    required: true,
    maxBytes: 256,
    enum: ["execution_failed", "persistence_failed", "interrupted", "cancelled"],
  });
  assert.deepEqual(turn?.failureMessage, { type: "nullableString", required: true, maxBytes: 4_096 });
  assert.deepEqual(turn?.failureRetryable, { type: "nullableBoolean", required: true });
});

test("shared request fixtures are validated against the contract params", async (context) => {
  const fixtures = await loadJson<FixtureDocument>("fixtures.json");
  const requests = fixtures.messages.filter(isRequestFixture);
  assert.ok(requests.some((fixture) => fixture.valid));
  assert.ok(requests.some((fixture) => !fixture.valid));
  for (const fixture of requests) {
    await context.test(fixture.name, () => {
      if (fixture.valid) {
        assert.doesNotThrow(() => parseProtocolMessage(fixture.message));
      } else {
        assert.throws(
          () => parseProtocolMessage(fixture.message),
          (error) => matchesExpectedError(error, fixture.errorCode),
        );
      }
    });
  }
});

test("a request missing a required param is rejected before it is sent", () => {
  assert.throws(
    () => parseProtocolMessage({
      protocolVersion: 1,
      messageType: "request",
      requestId,
      method: "session.rename",
      params: { projectId: "p1", sessionId: "28b222e0cc6543aa8d7bbdc423de99a7" },
    }),
    (error) => matchesExpectedError(error, "PROTOCOL_INVALID") &&
      /params\.title is required/.test((error as Error).message),
  );
});

test("envelopes are parsed without validating result or event data", () => {
  assert.doesNotThrow(() => parseProtocolMessage({
    protocolVersion: 1,
    messageType: "result",
    requestId,
    ok: true,
    data: { anyField: "Python validated this result before sending it" },
  }));
  assert.doesNotThrow(() => parseProtocolMessage({
    protocolVersion: 1,
    messageType: "event",
    requestId,
    sequence: 1,
    event: "stage.changed",
    data: { stage: "thinking" },
  }));

  const invalidEnvelopes: Array<[string, unknown, string]> = [
    ["unsupported version", { protocolVersion: 2, messageType: "result", requestId, ok: true, data: {} }, "PROTOCOL_VERSION_UNSUPPORTED"],
    ["unknown message type", { protocolVersion: 1, messageType: "notification", requestId }, "PROTOCOL_INVALID"],
    ["non-boolean ok", { protocolVersion: 1, messageType: "result", requestId, ok: "yes", data: {} }, "PROTOCOL_INVALID"],
    ["success with error", { protocolVersion: 1, messageType: "result", requestId, ok: true, data: {}, error: {} }, "PROTOCOL_INVALID"],
    ["failure with data", { protocolVersion: 1, messageType: "result", requestId, ok: false, data: {}, error: {} }, "PROTOCOL_INVALID"],
    ["non-canonical request id", { protocolVersion: 1, messageType: "result", requestId: "not-a-uuid", ok: true, data: {} }, "PROTOCOL_INVALID"],
    ["unknown error code", {
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: { code: "NOT_IN_CONTRACT", message: "x", retryable: false, details: {} },
    }, "PROTOCOL_INVALID"],
    ["oversized error message", {
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: { code: "INTERNAL_ERROR", message: "x".repeat(MAX_ERROR_MESSAGE_BYTES + 1), retryable: false, details: {} },
    }, "PROTOCOL_INVALID"],
    ["unknown request event", { protocolVersion: 1, messageType: "event", requestId, sequence: 1, event: "answer.chunk", data: {} }, "PROTOCOL_INVALID"],
    ["non-positive sequence", { protocolVersion: 1, messageType: "event", requestId, sequence: 0, event: "stage.changed", data: {} }, "PROTOCOL_INVALID"],
    ["unknown process event", { protocolVersion: 1, messageType: "event", event: "backend.unknown", data: {} }, "PROTOCOL_INVALID"],
    ["process event with sequence", { protocolVersion: 1, messageType: "event", sequence: 1, event: "backend.ready", data: {} }, "PROTOCOL_INVALID"],
  ];
  for (const [name, value, code] of invalidEnvelopes) {
    assert.throws(() => parseProtocolMessage(value), (error) => matchesExpectedError(error, code), name);
  }
});
