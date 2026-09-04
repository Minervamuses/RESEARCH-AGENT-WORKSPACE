import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  EVENT_DATA_SCHEMAS,
  FORBIDDEN_DATA_KEY_FRAGMENTS,
  MAX_ERROR_MESSAGE_BYTES,
  MAX_PROTOCOL_LINE_BYTES,
  MAX_REQUEST_ID_BYTES,
  METHOD_PARAM_SCHEMAS,
  METHOD_REQUIRED_PARAMS,
  PROCESS_EVENT_ORIGINS,
  PROCESS_EVENTS,
  PROTOCOL_ERROR_CODES,
  PROTOCOL_METHODS,
  PROTOCOL_VERSION,
  RESULT_DATA_SCHEMAS,
  ProtocolContractError,
  ProtocolTraceValidator,
  REQUEST_EVENTS,
  parseProtocolLine,
  parseProtocolMessage,
  parseProtocolMessageFromOrigin,
  validateProcessEventOrigin,
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
  maxLineBytes: number;
  requestIdMaxBytes: number;
  errorMessageMaxBytes: number;
  requestEvents: string[];
  processEvents: string[];
  processEventOrigins: Record<string, string[]>;
  forbiddenDataKeyFragments: string[];
  eventDataSchemas: Record<string, Record<string, ContractFieldRule>>;
  resultDataSchemas: Record<string, Record<string, ContractFieldRule>>;
  turnErrorDetailsSchema: Record<string, ContractFieldRule>;
  methods: ContractMethod[];
  errorCodes: string[];
}

interface MessageFixture {
  name: string;
  valid: boolean;
  errorCode?: string;
  message: unknown;
}

interface RawLineFixture {
  name: string;
  valid: boolean;
  errorCode?: string;
  line: string;
}

interface TraceFixture {
  name: string;
  valid: boolean;
  errorCode?: string;
  messages: unknown[];
}

interface OriginFixture {
  name: string;
  event: keyof typeof PROCESS_EVENT_ORIGINS;
  origin: "python" | "rust";
  valid: boolean;
  errorCode?: string;
}

interface FixtureDocument {
  messages: MessageFixture[];
  rawLines: RawLineFixture[];
  originCases: OriginFixture[];
  traces: TraceFixture[];
}

const currentDir = dirname(fileURLToPath(import.meta.url));
const protocolDir = resolve(currentDir, "../protocol/v1");

async function loadJson<T>(name: string): Promise<T> {
  return JSON.parse(await readFile(resolve(protocolDir, name), "utf8")) as T;
}

function matchesExpectedError(error: unknown, code: string | undefined): boolean {
  return error instanceof ProtocolContractError && error.code === code;
}

test("language-neutral manifest matches TypeScript constants", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const turnErrorDetailsSchema = (
    await import("../src/protocol.ts") as unknown as {
      TURN_ERROR_DETAILS_SCHEMA: Record<string, ContractFieldRule>;
    }
  ).TURN_ERROR_DETAILS_SCHEMA;
  assert.equal(contract.protocolVersion, PROTOCOL_VERSION);
  assert.equal(contract.maxLineBytes, MAX_PROTOCOL_LINE_BYTES);
  assert.equal(contract.requestIdMaxBytes, MAX_REQUEST_ID_BYTES);
  assert.equal(contract.errorMessageMaxBytes, MAX_ERROR_MESSAGE_BYTES);
  assert.deepEqual(contract.methods.map(({ name }) => name), [...PROTOCOL_METHODS]);
  assert.deepEqual(contract.requestEvents, [...REQUEST_EVENTS]);
  assert.deepEqual(contract.processEvents, [...PROCESS_EVENTS]);
  assert.deepEqual(contract.processEventOrigins, PROCESS_EVENT_ORIGINS);
  assert.deepEqual(contract.forbiddenDataKeyFragments, [...FORBIDDEN_DATA_KEY_FRAGMENTS]);
  assert.deepEqual(contract.eventDataSchemas, EVENT_DATA_SCHEMAS);
  assert.deepEqual(contract.resultDataSchemas, RESULT_DATA_SCHEMAS);
  assert.deepEqual(turnErrorDetailsSchema, {
    turnId: { type: "turnId", required: true },
    state: {
      type: "nullableString",
      required: true,
      enum: ["pending", "completed", "failed", "interrupted"],
    },
    accepted: { type: "boolean", required: true },
    persisted: { type: "boolean", required: true },
  });
  assert.deepEqual(contract.turnErrorDetailsSchema, turnErrorDetailsSchema);
  assert.deepEqual(contract.errorCodes, [...PROTOCOL_ERROR_CODES]);

  for (const method of contract.methods) {
    assert.deepEqual(
      method.requiredParams,
      METHOD_REQUIRED_PARAMS[method.name as keyof typeof METHOD_REQUIRED_PARAMS],
      method.name,
    );
    assert.deepEqual(
      method.params,
      METHOD_PARAM_SCHEMAS[method.name as keyof typeof METHOD_PARAM_SCHEMAS],
      method.name,
    );
    if (method.operation === "destructive") {
      assert.ok(method.requiredParams.includes("previewId"), method.name);
    }
  }

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
});

test("Product Plan Mode is retired while extended thinking remains", async () => {
  const contract = await loadJson<ContractDocument>("contract.json");
  const methodNames = new Set(contract.methods.map(({ name }) => name));
  assert.equal(methodNames.has("session.set_mode"), false);
  assert.equal(PROTOCOL_METHODS.includes("session.set_mode" as never), false);
  assert.equal("session.set_mode" in METHOD_PARAM_SCHEMAS, false);
  assert.equal(methodNames.has("session.set_thinking"), true);

  for (const method of ["session.create", "session.select"] as const) {
    const schema = RESULT_DATA_SCHEMAS[method];
    assert.equal("planMode" in schema, false);
    assert.equal("planLogPath" in schema, false);
    assert.deepEqual(schema.thinkingMode.enum, ["normal", "extended"]);
  }

  const appSource = await readFile(resolve(currentDir, "../src/App.tsx"), "utf8");
  assert.equal(appSource.includes("session.set_mode"), false);
  assert.equal(appSource.includes("Response mode"), false);
  assert.equal(appSource.includes("session.set_thinking"), true);
  assert.equal(appSource.includes('<option value="extended">Extended</option>'), true);
});

test("normal answers use only the final terminal result", () => {
  assert.equal(REQUEST_EVENTS.includes("answer.chunk" as never), false);
  assert.equal("answer.chunk" in EVENT_DATA_SCHEMAS, false);
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].streamKind, {
    type: "string",
    required: false,
    enum: ["final_only"],
  });
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].chunkCount, {
    type: "integer",
    required: false,
    minimum: 0,
    maximum: 0,
  });
});

test("session turn carries one canonical logical identity and durable lifecycle", () => {
  assert.deepEqual(METHOD_REQUIRED_PARAMS["session.turn"], ["text", "turnId", "retry"]);
  assert.deepEqual(METHOD_PARAM_SCHEMAS["session.turn"].turnId, {
    type: "turnId",
    required: true,
  });
  assert.deepEqual(METHOD_PARAM_SCHEMAS["session.turn"].retry, {
    type: "boolean",
    required: true,
  });
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].turnNumber, {
    type: "integer",
    required: true,
    minimum: 1,
    maximum: 4_096,
  });
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].state, {
    type: "string",
    required: true,
    enum: ["completed"],
  });
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].accepted, {
    type: "boolean",
    required: true,
  });
  assert.deepEqual(RESULT_DATA_SCHEMAS["session.turn"].persisted, {
    type: "boolean",
    required: true,
  });
  assert.equal(PROTOCOL_ERROR_CODES.includes("CONVERSATION_FLUSH_FAILED" as never), false);
  assert.equal(PROTOCOL_ERROR_CODES.includes("SHUTDOWN_FLUSH_FAILED" as never), false);
});

test("extension apply carries its own canonical durable turn lifecycle", () => {
  assert.deepEqual(METHOD_REQUIRED_PARAMS["extensions.apply"], [
    "previewId",
    "approvedBindingHashes",
    "turnId",
    "retry",
  ]);
  assert.deepEqual(METHOD_PARAM_SCHEMAS["extensions.apply"].turnId, {
    type: "turnId",
    required: true,
  });
  assert.deepEqual(METHOD_PARAM_SCHEMAS["extensions.apply"].retry, {
    type: "boolean",
    required: true,
  });
  const result = RESULT_DATA_SCHEMAS["extensions.apply"];
  assert.deepEqual(result.turnId, { type: "turnId", required: true });
  assert.deepEqual(result.turnNumber, {
    type: "integer",
    required: true,
    minimum: 1,
    maximum: 4_096,
  });
  assert.deepEqual(result.state, {
    type: "string",
    required: true,
    enum: ["completed"],
  });
  assert.deepEqual(result.accepted, { type: "boolean", required: true });
  assert.deepEqual(result.persisted, { type: "boolean", required: true });
});

test("session summaries and transcripts expose canonical lifecycle state", () => {
  const summary = RESULT_DATA_SCHEMAS["session.list"]?.items.items;
  assert.deepEqual(summary?.createdAt, {
    type: "nullableString",
    required: true,
    maxBytes: 64,
  });

  const turn = RESULT_DATA_SCHEMAS["session.transcript"]?.items.items;
  assert.deepEqual(Object.keys(turn ?? {}).sort(), [
    "turnId",
    "turnNumber",
    "kind",
    "state",
    "timestamp",
    "userText",
    "assistantText",
    "failureCode",
    "failureMessage",
    "failureRetryable",
    "toolActivities",
  ].sort());
  assert.deepEqual(turn?.turnId, { type: "turnId", required: true });
  assert.deepEqual(turn?.kind, {
    type: "string",
    required: true,
    enum: ["conversational", "display-only"],
  });
  assert.deepEqual(turn?.state, {
    type: "string",
    required: true,
    enum: ["pending", "completed", "failed", "interrupted"],
  });
  assert.deepEqual(turn?.timestamp, { type: "utcTimestamp", required: true });
  assert.deepEqual(turn?.assistantText, {
    type: "nullableString",
    required: true,
    maxBytes: 32_768,
  });
  assert.deepEqual(turn?.failureCode, {
    type: "nullableString",
    required: true,
    maxBytes: 256,
    enum: ["execution_failed", "persistence_failed", "interrupted", "cancelled"],
  });
  assert.deepEqual(turn?.failureMessage, {
    type: "nullableString",
    required: true,
    maxBytes: 4_096,
  });
  assert.deepEqual(turn?.failureRetryable, { type: "nullableBoolean", required: true });
});

test("shared process-event origin fixtures", async (context) => {
  const fixtures = await loadJson<FixtureDocument>("fixtures.json");
  for (const fixture of fixtures.originCases) {
    await context.test(fixture.name, () => {
      if (fixture.valid) {
        assert.doesNotThrow(() => validateProcessEventOrigin(fixture.event, fixture.origin));
        assert.doesNotThrow(() =>
          parseProtocolMessageFromOrigin(
            {
              protocolVersion: 1,
              messageType: "event",
              event: fixture.event,
              data: {},
            },
            fixture.origin,
          ),
        );
      } else {
        assert.throws(
          () => validateProcessEventOrigin(fixture.event, fixture.origin),
          (error) => matchesExpectedError(error, fixture.errorCode),
        );
        assert.throws(
          () =>
            parseProtocolMessageFromOrigin(
              {
                protocolVersion: 1,
                messageType: "event",
                event: fixture.event,
                data: {},
              },
              fixture.origin,
            ),
          (error) => matchesExpectedError(error, fixture.errorCode),
        );
      }
    });
  }
});

test("shared message fixtures", async (context) => {
  const fixtures = await loadJson<FixtureDocument>("fixtures.json");
  for (const fixture of fixtures.messages) {
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

test("shared raw-line fixtures and line limit", async (context) => {
  const fixtures = await loadJson<FixtureDocument>("fixtures.json");
  for (const fixture of fixtures.rawLines) {
    await context.test(fixture.name, () => {
      if (fixture.valid) {
        assert.doesNotThrow(() => parseProtocolLine(fixture.line));
      } else {
        assert.throws(
          () => parseProtocolLine(fixture.line),
          (error) => matchesExpectedError(error, fixture.errorCode),
        );
      }
    });
  }

  const oversized = JSON.stringify({ padding: "x".repeat(MAX_PROTOCOL_LINE_BYTES) });
  assert.throws(
    () => parseProtocolLine(oversized),
    (error) => matchesExpectedError(error, "PROTOCOL_INVALID"),
  );
});

test("shared ordering and correlation traces", async (context) => {
  const fixtures = await loadJson<FixtureDocument>("fixtures.json");
  for (const fixture of fixtures.traces) {
    await context.test(fixture.name, () => {
      const validator = new ProtocolTraceValidator();
      const run = () => {
        for (const value of fixture.messages) {
          validator.accept(parseProtocolMessage(value));
        }
      };
      if (fixture.valid) {
        assert.doesNotThrow(run);
      } else {
        assert.throws(run, (error) => matchesExpectedError(error, fixture.errorCode));
      }
    });
  }
});
