// U16: the hand-written TS DTOs must follow contract.json. Python is the only
// runtime schema validator (U1), so a contract field that changes without its
// DTO would otherwise reach the UI as `undefined` while tests still pass.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import ts from "typescript";

interface FieldRule {
  type: string;
  required: boolean;
  enum?: string[];
  items?: FieldSchema;
}

type FieldSchema = Record<string, FieldRule>;

interface ContractDocument {
  methods: { name: string }[];
  requestEvents: string[];
  processEvents: string[];
  resultDataSchemas: Record<string, FieldSchema>;
  eventDataSchemas: Record<string, FieldSchema>;
  submittedContextSchema: FieldSchema;
  documentApprovalDataSchema: FieldSchema;
}

const desktopDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const contract = JSON.parse(
  readFileSync(resolve(desktopDir, "protocol/v1/contract.json"), "utf8"),
) as ContractDocument;

/**
 * Contract entries without a DTO, each with its reason. Expected to stay empty;
 * C4 removed the vocabulary that used to be listed here.
 */
const DTO_EXCEPTIONS: Readonly<Record<string, string>> = {};

/** Methods without a result schema; they must stay out of `MethodResults`. */
const METHODS_WITHOUT_RESULT_SCHEMA = [
  "session.set_thinking",
];

/**
 * `approval.required` has two wire shapes chosen by Python: a command approval
 * (`eventDataSchemas`) and a document approval (`documentApprovalDataSchema`).
 * The single DTO is their merge: a field is required only when both require it.
 */
function mergeVariantSchemas(variants: readonly FieldSchema[]): FieldSchema {
  const merged: FieldSchema = {};
  for (const name of new Set(variants.flatMap((schema) => Object.keys(schema)))) {
    const rules = variants.map((schema) => schema[name]);
    const present = rules.filter((rule): rule is FieldRule => rule !== undefined);
    merged[name] = { ...present[0], required: rules.every((rule) => rule?.required === true) };
  }
  return merged;
}

const EVENT_SCHEMAS: Record<string, FieldSchema> = {
  ...contract.eventDataSchemas,
  "approval.required": mergeVariantSchemas([
    contract.eventDataSchemas["approval.required"],
    contract.documentApprovalDataSchema,
  ]),
};

const STRING_TYPES = new Set(["string", "turnId", "requestId", "utcTimestamp"]);

function flatten(type: ts.Type): ts.Type[] {
  return type.isUnion() ? type.types : [type];
}

function isNullish(type: ts.Type): boolean {
  return (type.flags & (ts.TypeFlags.Null | ts.TypeFlags.Undefined)) !== 0;
}

/**
 * Compare a DTO with one contract object schema; returns readable mismatches.
 * A union of object types (for example the `Reference` discriminated union) is
 * compared as the merge of its variants: a field only some variants declare is
 * optional, and a field's type is the union of the variants' types.
 */
function compareObject(
  checker: ts.TypeChecker,
  variants: readonly ts.Type[],
  schema: FieldSchema,
  submittedContextSchema: FieldSchema,
  path: string,
): string[] {
  const problems: string[] = [];
  const names = new Set(variants.flatMap((variant) => checker.getPropertiesOfType(variant).map(({ name }) => name)));
  for (const name of Object.keys(schema)) {
    if (!names.has(name)) problems.push(`${path}.${name}: missing from the DTO`);
  }
  for (const name of names) {
    if (!(name in schema)) problems.push(`${path}.${name}: not in the contract schema`);
  }
  for (const [name, rule] of Object.entries(schema)) {
    if (!names.has(name)) continue;
    const symbols = variants.map((variant) => checker.getPropertyOfType(variant, name));
    const present = symbols.filter((symbol): symbol is ts.Symbol => symbol !== undefined);
    const optional = present.length < variants.length ||
      present.some((symbol) => (symbol.flags & ts.SymbolFlags.Optional) !== 0);
    if (optional === rule.required) {
      problems.push(`${path}.${name}: contract required=${rule.required} but DTO is ${optional ? "optional" : "required"}`);
    }
    const types = present.flatMap((symbol) => flatten(checker.getTypeOfSymbol(symbol)));
    problems.push(...compareField(checker, types, rule, submittedContextSchema, `${path}.${name}`));
  }
  return problems;
}

function compareField(
  checker: ts.TypeChecker,
  types: readonly ts.Type[],
  rule: FieldRule,
  submittedContextSchema: FieldSchema,
  path: string,
): string[] {
  const nullable = rule.type.startsWith("nullable");
  const base = nullable ? rule.type[8].toLowerCase() + rule.type.slice(9) : rule.type;
  const problems: string[] = [];
  const includesNull = types.some((part) => (part.flags & ts.TypeFlags.Null) !== 0);
  if (includesNull !== nullable) {
    problems.push(`${path}: contract ${nullable ? "allows" : "forbids"} null but DTO ${includesNull ? "includes" : "omits"} it`);
  }
  const parts = types.filter((part) => !isNullish(part));
  const shown = parts.map((part) => checker.typeToString(part)).join(" | ") || "nothing";
  if (STRING_TYPES.has(base)) {
    if (rule.enum !== undefined) {
      const expected = [...rule.enum].sort();
      const actual = [...new Set(parts.filter((part) => part.isStringLiteral()).map((part) => (part as ts.StringLiteralType).value))].sort();
      if (parts.some((part) => !part.isStringLiteral()) || JSON.stringify(actual) !== JSON.stringify(expected)) {
        problems.push(`${path}: enum ${JSON.stringify(expected)} but DTO is ${shown}`);
      }
    } else if (parts.length === 0 || parts.some((part) => (part.flags & ts.TypeFlags.String) === 0)) {
      problems.push(`${path}: expected string but DTO is ${shown}`);
    }
    return problems;
  }
  if (base === "integer") {
    if (parts.length === 0 || parts.some((part) => (part.flags & ts.TypeFlags.NumberLike) === 0)) {
      problems.push(`${path}: expected number but DTO is ${shown}`);
    }
    return problems;
  }
  if (base === "boolean") {
    if (parts.length === 0 || parts.some((part) => (part.flags & ts.TypeFlags.BooleanLike) === 0)) {
      problems.push(`${path}: expected boolean but DTO is ${shown}`);
    }
    return problems;
  }
  if (base === "stringArray" || base === "objectArray") {
    if (parts.length === 0 || parts.some((part) => !checker.isArrayType(part))) {
      problems.push(`${path}: expected an array but DTO is ${shown}`);
      return problems;
    }
    const elements = parts.flatMap((part) => flatten(checker.getIndexTypeOfType(part, ts.IndexKind.Number)!));
    if (base === "stringArray") {
      if (elements.some((element) => (element.flags & ts.TypeFlags.String) === 0)) {
        problems.push(`${path}[]: expected string but DTO is ${elements.map((element) => checker.typeToString(element)).join(" | ")}`);
      }
      return problems;
    }
    return [...problems, ...compareObject(checker, elements, rule.items ?? {}, submittedContextSchema, `${path}[]`)];
  }
  if (base === "object" || base === "submittedContext") {
    if (parts.length === 0 || parts.some((part) => (part.flags & (ts.TypeFlags.Object | ts.TypeFlags.Intersection)) === 0)) {
      problems.push(`${path}: expected an object but DTO is ${shown}`);
      return problems;
    }
    const schema = base === "object" ? rule.items ?? {} : submittedContextSchema;
    return [...problems, ...compareObject(checker, parts, schema, submittedContextSchema, path)];
  }
  return [...problems, `${path}: unsupported contract type ${rule.type}`];
}

function compilerOptions(): ts.CompilerOptions {
  const configPath = resolve(desktopDir, "tsconfig.json");
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  return ts.parseJsonConfigFileContent(config.config, ts.sys, desktopDir).options;
}

/** Declared type of an exported interface or type alias. */
function exportedType(checker: ts.TypeChecker, sourceFile: ts.SourceFile, name: string): ts.Type {
  const moduleSymbol = checker.getSymbolAtLocation(sourceFile)!;
  const symbol = checker.getExportsOfModule(moduleSymbol).find((item) => item.name === name);
  assert.ok(symbol, `${sourceFile.fileName} exports ${name}`);
  return checker.getDeclaredTypeOfSymbol(symbol);
}

function stringLiteralUnion(type: ts.Type): string[] {
  return (type.isUnion() ? type.types : [type])
    .map((part) => (part.isStringLiteral() ? part.value : `<non-literal ${part.flags}>`))
    .sort();
}

function inMemoryChecker(source: string): { checker: ts.TypeChecker; sourceFile: ts.SourceFile } {
  const fileName = resolve(desktopDir, "__virtual__/dtos.ts");
  const options = { ...compilerOptions(), noUnusedLocals: false };
  const host = ts.createCompilerHost(options);
  const original = { getSourceFile: host.getSourceFile, fileExists: host.fileExists, readFile: host.readFile };
  host.getSourceFile = (name, languageVersion, ...rest) =>
    name === fileName
      ? ts.createSourceFile(name, source, languageVersion)
      : original.getSourceFile.call(host, name, languageVersion, ...rest);
  host.fileExists = (name) => name === fileName || original.fileExists.call(host, name);
  host.readFile = (name) => (name === fileName ? source : original.readFile.call(host, name));
  const program = ts.createProgram([fileName], options, host);
  return { checker: program.getTypeChecker(), sourceFile: program.getSourceFile(fileName)! };
}

const UNIT_SCHEMA: FieldSchema = {
  id: { type: "string", required: true },
  count: { type: "integer", required: false },
  note: { type: "nullableString", required: true },
  mode: { type: "string", required: true, enum: ["ask", "bypass"] },
  tags: { type: "stringArray", required: true },
  child: { type: "object", required: true, items: { flag: { type: "boolean", required: true } } },
  rows: { type: "objectArray", required: true, items: { turnId: { type: "turnId", required: true } } },
};

const UNIT_MATCHING_DTO = `
  interface Base { id: string }
  export interface Dto extends Base {
    count?: number;
    note: string | null;
    mode: "ask" | "bypass";
    tags: readonly string[];
    child: { flag: boolean };
    rows: { turnId: string }[];
  }
`;

function unitProblems(dtoSource: string): string[] {
  const { checker, sourceFile } = inMemoryChecker(dtoSource);
  return compareObject(checker, [exportedType(checker, sourceFile, "Dto")], UNIT_SCHEMA, {}, "Dto");
}

test("DTO comparator accepts a matching DTO, including inherited fields and readonly arrays", () => {
  assert.deepEqual(unitProblems(UNIT_MATCHING_DTO), []);
});

test("DTO comparator merges discriminated union variants", () => {
  const schema: FieldSchema = {
    kind: { type: "string", required: true, enum: ["a", "b"] },
    a: { type: "object", required: false, items: { x: { type: "integer", required: true } } },
    b: { type: "string", required: false },
  };
  const { checker, sourceFile } = inMemoryChecker(
    'export type Dto = { kind: "a"; a: { x: number } } | { kind: "b"; b: string };',
  );
  assert.deepEqual(compareObject(checker, flatten(exportedType(checker, sourceFile, "Dto")), schema, {}, "Dto"), []);
  const drifted = inMemoryChecker('export type Dto = { kind: "a"; a: { x: number } } | { kind: "c"; b: string };');
  assert.ok(compareObject(drifted.checker, flatten(exportedType(drifted.checker, drifted.sourceFile, "Dto")), schema, {}, "Dto")
    .some((problem) => /Dto\.kind: enum/.test(problem)));
});

test("DTO comparator detects each kind of drift", () => {
  const cases: Array<[string, string, RegExp]> = [
    ["missing field", UNIT_MATCHING_DTO.replace("count?: number;", ""), /Dto\.count: missing from the DTO/],
    ["extra field", UNIT_MATCHING_DTO.replace("count?: number;", "count?: number; extra: string;"), /Dto\.extra: not in the contract schema/],
    ["required made optional", UNIT_MATCHING_DTO.replace("note: string | null;", "note?: string | null;"), /Dto\.note: contract required=true but DTO is optional/],
    ["optional made required", UNIT_MATCHING_DTO.replace("count?: number;", "count: number;"), /Dto\.count: contract required=false but DTO is required/],
    ["missing null", UNIT_MATCHING_DTO.replace("note: string | null;", "note: string;"), /Dto\.note: contract allows null but DTO omits it/],
    ["different enum member", UNIT_MATCHING_DTO.replace('mode: "ask" | "bypass";', 'mode: "ask" | "auto";'), /Dto\.mode: enum/],
    ["nested object field", UNIT_MATCHING_DTO.replace("child: { flag: boolean };", "child: { flags: boolean };"), /Dto\.child\.flag: missing from the DTO/],
    ["nested array item field", UNIT_MATCHING_DTO.replace("rows: { turnId: string }[];", "rows: { turnId: number }[];"), /Dto\.rows\[\]\.turnId: expected string/],
  ];
  for (const [name, source, expected] of cases) {
    const problems = unitProblems(source);
    assert.ok(problems.some((problem) => expected.test(problem)), `${name}: ${JSON.stringify(problems)}`);
  }
});

test("TS protocol DTOs, method names, and event names follow contract.json", () => {
  const started = performance.now();
  const options = compilerOptions();
  const protocolPath = resolve(desktopDir, "src/protocol.ts");
  const program = ts.createProgram([protocolPath], options);
  const checker = program.getTypeChecker();
  const sourceFile = program.getSourceFile(protocolPath)!;

  for (const reason of Object.values(DTO_EXCEPTIONS)) assert.ok(reason.length > 0);

  assert.deepEqual(
    stringLiteralUnion(exportedType(checker, sourceFile, "ProtocolMethod")),
    contract.methods.map(({ name }) => name).sort(),
    "ProtocolMethod equals the contract methods",
  );
  assert.deepEqual(
    stringLiteralUnion(exportedType(checker, sourceFile, "RequestEvent")),
    [...contract.requestEvents].sort(),
    "RequestEvent equals the contract request events",
  );
  assert.deepEqual(
    stringLiteralUnion(exportedType(checker, sourceFile, "ProcessEvent")),
    [...contract.processEvents].sort(),
    "ProcessEvent equals the contract process events",
  );

  const problems: string[] = [];
  const methodResults = exportedType(checker, sourceFile, "MethodResults");
  const resultEntries = new Map(checker.getPropertiesOfType(methodResults).map((symbol) => [symbol.name, symbol]));
  const expectedMethods = Object.keys(contract.resultDataSchemas)
    .filter((method) => !(`method:${method}` in DTO_EXCEPTIONS)).sort();
  assert.deepEqual([...resultEntries.keys()].sort(), expectedMethods, "MethodResults covers every result schema");
  assert.deepEqual(
    contract.methods.map(({ name }) => name).filter((name) => !(name in contract.resultDataSchemas)).sort(),
    [...METHODS_WITHOUT_RESULT_SCHEMA].sort(),
    "methods without a result schema are listed explicitly",
  );
  for (const [method, symbol] of resultEntries) {
    problems.push(...compareObject(
      checker, flatten(checker.getTypeOfSymbol(symbol)), contract.resultDataSchemas[method],
      contract.submittedContextSchema, `MethodResults["${method}"]`,
    ));
  }

  const eventData = exportedType(checker, sourceFile, "EventData");
  const eventEntries = new Map(checker.getPropertiesOfType(eventData).map((symbol) => [symbol.name, symbol]));
  const expectedEvents = Object.keys(contract.eventDataSchemas)
    .filter((event) => !(`event:${event}` in DTO_EXCEPTIONS)).sort();
  assert.deepEqual([...eventEntries.keys()].sort(), expectedEvents, "EventData covers every event data schema");
  for (const [event, symbol] of eventEntries) {
    problems.push(...compareObject(
      checker, flatten(checker.getTypeOfSymbol(symbol)), EVENT_SCHEMAS[event],
      contract.submittedContextSchema, `EventData["${event}"]`,
    ));
  }

  assert.deepEqual(problems, [], `DTOs drifted from contract.json:\n${problems.join("\n")}`);
  console.log(`protocol DTO check: ${resultEntries.size} results, ${eventEntries.size} events in ${(performance.now() - started).toFixed(0)} ms`);
});
