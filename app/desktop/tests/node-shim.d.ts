// Minimal typings for the Node built-ins the tests import. The project adds no
// npm dependency (so no @types/node); these mirror the @types/node signatures
// for exactly the calls the tests make, so tsc still checks every assertion.
declare module "node:assert/strict" {
  type ErrorMatcher = RegExp | (new (...args: never[]) => Error) | ((error: unknown) => boolean) | object;
  interface Assert {
    (value: unknown, message?: string | Error): asserts value;
    ok(value: unknown, message?: string | Error): asserts value;
    equal<T>(actual: unknown, expected: T, message?: string | Error): asserts actual is T;
    notEqual(actual: unknown, expected: unknown, message?: string | Error): void;
    deepEqual<T>(actual: unknown, expected: T, message?: string | Error): asserts actual is T;
    match(value: string, regExp: RegExp, message?: string | Error): void;
    doesNotMatch(value: string, regExp: RegExp, message?: string | Error): void;
    throws(block: () => unknown, error?: ErrorMatcher, message?: string | Error): void;
    doesNotThrow(block: () => unknown, message?: string | Error): void;
    rejects(block: (() => Promise<unknown>) | Promise<unknown>, error?: ErrorMatcher, message?: string | Error): Promise<void>;
    fail(message?: string | Error): never;
  }
  const assert: Assert;
  export default assert;
}

declare module "node:test" {
  export interface TestContext {
    name: string;
    test(name: string, fn: (context: TestContext) => void | Promise<void>): Promise<void>;
  }
  export default function test(name: string, fn: (context: TestContext) => void | Promise<void>): Promise<void>;
  export function after(fn: () => void | Promise<void>): void;
}

declare module "node:fs/promises" {
  export function readFile(path: string | URL, encoding: "utf8"): Promise<string>;
}

declare module "node:fs" {
  export function readFileSync(path: string | URL, encoding: "utf8"): string;
}

declare module "node:path" {
  export function dirname(path: string): string;
  export function resolve(...paths: string[]): string;
}

declare module "node:url" {
  export function fileURLToPath(url: string | URL): string;
}

declare function setImmediate(callback: () => void): unknown;

interface ImportMeta {
  url: string;
}
