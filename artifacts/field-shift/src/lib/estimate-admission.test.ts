import test from "node:test";
import assert from "node:assert/strict";
import { estimateAdmission, secondsUntil } from "./estimate-admission.ts";

test("admission busy and cooldown carry explicit retry times, not input failures", () => {
  for (const code of ["estimate_busy", "estimate_cooldown"]) {
    assert.deepEqual(estimateAdmission({
      status: 429, data: { detail: { code, retryAfterSeconds: 12, message: "Wait, not a data failure." } },
    }), { code, retryAfterSeconds: 12, message: "Wait, not a data failure." });
  }
  assert.equal(estimateAdmission({ status: 503 }), null);
  assert.equal(estimateAdmission({ status: 422 }), null);
});

test("old servers and malformed delays still get a bounded visible wait", () => {
  assert.equal(estimateAdmission({ status: 429, data: { detail: "Wait 30 seconds." } })?.retryAfterSeconds, 30);
  assert.equal(estimateAdmission({ status: 429, headers: new Headers({ "Retry-After": "7" }) })?.retryAfterSeconds, 7);
  assert.equal(estimateAdmission({ status: 429, data: { detail: { retryAfterSeconds: NaN } } })?.retryAfterSeconds, 30);
});

test("countdown rounds up and unlocks only after the deadline", () => {
  assert.equal(secondsUntil(30_000, 0), 30);
  assert.equal(secondsUntil(30_000, 29_999), 1);
  assert.equal(secondsUntil(30_000, 30_000), 0);
  assert.equal(secondsUntil(30_000, 31_000), 0);
});
