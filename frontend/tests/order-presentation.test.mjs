import test from "node:test";
import assert from "node:assert/strict";
import { acceptanceDeadline, creditLabel, formatOrderDate, shortOrderId, statusLabel, statusTone } from "../src/utils/orderPresentation.js";

test("deadline labels close expired orders and round remaining minutes up", () => {
  const now = Date.parse("2026-10-25T08:00:00Z");
  assert.equal(acceptanceDeadline("2026-10-25T07:59:59Z", now), "Acceptance closed");
  assert.equal(acceptanceDeadline("2026-10-25T08:00:00Z", now), "Acceptance closed");
  assert.equal(acceptanceDeadline("2026-10-25T08:00:01Z", now), "Accept within 1 min");
  assert.equal(acceptanceDeadline("2026-10-25T08:20:01Z", now), "Accept within 21 min");
  assert.equal(acceptanceDeadline("2026-10-25T09:01:00Z", now), "Accept within 1 hr 1 min");
  assert.equal(acceptanceDeadline("invalid", now), "Deadline unavailable");
});

test("compact dates use campus time while detailed dates retain year and seconds", () => {
  assert.match(formatOrderDate("2026-10-25T08:12:05Z"), /25 Oct.*16:12/);
  assert.match(formatOrderDate("2026-10-25T08:12:05Z", { detailed: true }), /2026.*16:12:05/);
  assert.equal(formatOrderDate("invalid"), "Not available");
});

test("order labels preserve lifecycle distinctions and singular credit rewards", () => {
  assert.equal(statusLabel("PICKED_UP"), "Picked up");
  assert.equal(statusLabel("COMPLETING"), "Processing reward");
  assert.equal(statusTone("COMPLETED"), "success");
  assert.equal(statusTone("EXPIRED"), "neutral");
  assert.equal(statusTone("REJECTED"), "danger");
  assert.equal(creditLabel(1), "1 credit");
  assert.equal(creditLabel(2), "2 credits");
  assert.equal(shortOrderId("812a77d9-d40b-408e-b106-a8d8695b34d6"), "812a77d9");
});
