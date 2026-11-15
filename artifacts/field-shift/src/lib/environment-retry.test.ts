import test from "node:test";
import assert from "node:assert/strict";
import { retryEnvironment, environmentRetryDelay } from "./environment-retry.ts";

test("in-progress data retrieval waits automatically, but is bounded", () => {
  for (let count = 0; count < 6; count++) {
    assert.equal(retryEnvironment(count, { status: 409 }), true);
  }
  assert.equal(retryEnvironment(6, { status: 409 }), false);
  assert.equal(environmentRetryDelay(0, { status: 409 }), 2000);
  assert.equal(environmentRetryDelay(5, { status: 409 }), 20_000);
});

test("validation, authorization and admission failures are not hammered", () => {
  for (const status of [400, 401, 403, 404, 422, 429]) {
    assert.equal(retryEnvironment(0, { status }), false);
  }
});

test("network and server failures retain one ordinary retry", () => {
  for (const error of [new Error("synthetic timeout"), { status: 503 }, undefined]) {
    assert.equal(retryEnvironment(0, error), true);
    assert.equal(retryEnvironment(1, error), false);
    assert.equal(environmentRetryDelay(0, error), 1000);
  }
});
