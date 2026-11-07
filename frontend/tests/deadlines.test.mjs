import test from "node:test";
import assert from "node:assert/strict";
import { closingNotice, deadlineChoices, deadlineMinutes, effectiveDeadline } from "../src/utils/deadlines.js";

const now = new Date("2026-11-09T20:00:00+08:00");
const available = (closesAt) => deadlineChoices(closesAt, now)
  .filter((choice) => choice.available).map((choice) => choice.minutes);

test("a store that never closes offers every deadline", () => {
  assert.deepEqual(available(null), [30, 45, 60]);
  assert.equal(closingNotice(null, deadlineChoices(null, now)), "");
});

test("deadlines must end 10 minutes before closing", () => {
  assert.deepEqual(available("2026-11-09T21:10:00+08:00"), [30, 45, 60]);
  assert.deepEqual(available("2026-11-09T21:00:00+08:00"), [30, 45]);
  assert.deepEqual(available("2026-11-09T20:40:00+08:00"), [30]);
  assert.deepEqual(available("2026-11-09T20:39:00+08:00"), []);
});

test("an unavailable choice falls back to the longest that fits", () => {
  const choices = deadlineChoices("2026-11-09T21:00:00+08:00", now);
  assert.equal(effectiveDeadline(choices, "Within 1 hour").label, "Within 45 mins");
  assert.equal(effectiveDeadline(choices, "Within 30 mins").label, "Within 30 mins");
  assert.equal(effectiveDeadline(deadlineChoices("2026-11-09T20:20:00+08:00", now), "Within 30 mins"), null);
});

test("the notice gives closing and last acceptance times in campus time", () => {
  const closes = "2026-11-09T21:00:00+08:00";
  assert.equal(closingNotice(closes, deadlineChoices(closes, now)),
    "This store closes at 21:00, so a courier must accept by 20:50.");
  const soon = "2026-11-09T20:20:00+08:00";
  assert.match(closingNotice(soon, deadlineChoices(soon, now)), /closes at 20:20, too soon/);
});

test("labels map to the minutes sent as expires_at", () => {
  assert.equal(deadlineMinutes("Within 30 mins"), 30);
  assert.equal(deadlineMinutes("Within 1 hour"), 60);
});
