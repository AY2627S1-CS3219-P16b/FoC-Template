import test from "node:test";
import assert from "node:assert/strict";
import { contactWarning } from "../src/utils/contactWarning.js";

test("profile warns when the chosen contact method would share nothing", () => {
  assert.match(contactWarning({ contact_preference: "", telegram_handle: "@me" }), /Choose a preferred contact method/);
  assert.match(contactWarning({ contact_preference: "TELEGRAM", telegram_handle: "  " }), /Telegram handle/);
  assert.match(contactWarning({ contact_preference: "PHONE", phone_number: "" }), /phone number/);
});

test("no warning when the chosen method has a value, or is email", () => {
  assert.equal(contactWarning({ contact_preference: "TELEGRAM", telegram_handle: "@me" }), "");
  assert.equal(contactWarning({ contact_preference: "PHONE", phone_number: "91234567" }), "");
  assert.equal(contactWarning({ contact_preference: "EMAIL" }), "");
});
