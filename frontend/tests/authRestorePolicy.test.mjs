import { test } from "node:test";
import assert from "node:assert/strict";
import { classifySessionRestoreError, getProtectedRouteState } from "../src/utils/authRestorePolicy.js";

test("temporary network/timeout/service outage is never classified as signed-out", () => {
  for (const error of [
    { code: "ECONNABORTED" },
    { response: { status: 503 } },
    { response: { status: 502 } },
    { response: { status: 403 } },
    {},
  ]) {
    assert.equal(classifySessionRestoreError(error), "retryable");
  }
});

test("only a verified 401 invalidates a session", () => {
  assert.equal(classifySessionRestoreError({ response: { status: 401 } }), "invalid");
});

test("transient session failure preserves current route instead of navigating to login", () => {
  assert.equal(getProtectedRouteState({ user: null, isLoading: false, restoreError: true, hasToken: true }), "reconnect");
  assert.equal(getProtectedRouteState({ user: null, isLoading: true, restoreError: false, hasToken: true }), "loading");
});

test("valid session opens page; explicit sign-out still redirects to login", () => {
  assert.equal(getProtectedRouteState({ user: { id: 11 }, isLoading: false, restoreError: false, hasToken: true }), "ready");
  assert.equal(getProtectedRouteState({ user: null, isLoading: false, restoreError: false, hasToken: false }), "login");
  assert.equal(getProtectedRouteState({ user: null, isLoading: false, restoreError: true, hasToken: false }), "login");
});
