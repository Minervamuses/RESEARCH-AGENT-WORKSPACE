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
