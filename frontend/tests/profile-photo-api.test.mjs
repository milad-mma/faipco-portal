import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const src = readFileSync(fileURLToPath(new URL("../src/api/employees.js", import.meta.url)), "utf8");
const match = src.match(/export async function fetchEmployeePhotoThumbnailBlob\(employeeId, signal\) \{[\s\S]*?\n\}/);
assert.ok(match, "photo API function should declare its optional abort signal");
const calls = [];
const client = { get: async (...args) => { calls.push(args); return { data: new Blob(["ok"]) }; } };
const fn = new Function("apiClient", `return (${match[0].replace(/^export /, "")})`)(client);

test("photo request works without optional signal", async () => {
  const blob = await fn(42);
  assert.ok(blob instanceof Blob);
  assert.equal(calls.at(-1)[0], "/employees/42/photo-thumbnail");
  assert.equal(calls.at(-1)[1].signal, undefined);
  assert.equal(calls.at(-1)[1].responseType, "blob");
});

test("photo request forwards provided AbortSignal", async () => {
  const controller = new AbortController();
  await fn(42, controller.signal);
  assert.equal(calls.at(-1)[1].signal, controller.signal);
});

const birthdayMatch = src.match(/export async function fetchBirthdayPhotoThumbnailBlob\(employeeId, signal\) \{[\s\S]*?\n\}/);
assert.ok(birthdayMatch, "birthday API should accept cancellation signal");
const birthdayCalls = [];
const birthdayClient = { get: async (...args) => { birthdayCalls.push(args); return { data: new Blob(["photo"]) }; } };
const birthdayFn = new Function("apiClient", `return (${birthdayMatch[0].replace(/^export /, "")})`)(birthdayClient);
test("birthday photo forwards AbortSignal to transport", async () => {
  const ctrl = new AbortController();
  await birthdayFn(19, ctrl.signal);
  assert.equal(birthdayCalls[0][0], "/employees/birthday-photo/19");
  assert.equal(birthdayCalls[0][1].signal, ctrl.signal);
});
