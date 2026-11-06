import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ORDER_STATUS_LABELS } from "../src/utils/orderPresentation.js";
import { helpOrderChoices, orderHelpContext, orderHelpTopics, publishHelpOrders, subscribeHelpOrders } from "../src/utils/orderHelp.js";

const docsDir = fileURLToPath(new URL("../../faq-service/docs/", import.meta.url));
const faqQuestions = new Set(readdirSync(docsDir)
  .filter((name) => name.endsWith(".md") && name !== "README.md")
  .flatMap((name) => readFileSync(docsDir + name, "utf8").split("\n"))
  .filter((line) => line.startsWith("## "))
  .map((line) => line.slice(3).trim()));

const statuses = Object.keys(ORDER_STATUS_LABELS);
const courierStatuses = ["ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED"];

test("every suggested question is an FAQ heading, so Help retrieves its answer", () => {
  for (const [role, list] of [["requester", statuses], ["courier", courierStatuses]]) {
    for (const status of list) {
      const { summary, questions } = orderHelpTopics(status, role);
      assert.ok(summary, `${role} ${status} has a summary`);
      assert.ok(questions.length >= 1 && questions.length <= 3, `${role} ${status} has 1-3 questions`);
      for (const question of questions) {
        assert.ok(faqQuestions.has(question), `"${question}" (${role} ${status}) must match an FAQ heading`);
      }
    }
  }
});

test("requester help follows the errand from pickup to delivery", () => {
  assert.match(orderHelpTopics("ACCEPTED", "requester").summary, /heading to the store/);
  assert.match(orderHelpTopics("PICKED_UP", "requester").summary, /on the way to you/);
  assert.ok(orderHelpTopics("PICKED_UP", "requester").questions.includes("Where is my courier?"));
  assert.ok(orderHelpTopics("DELIVERED", "requester").questions
    .includes("It says delivered, but I didn't receive my items. What should I do?"));
  assert.deepEqual(orderHelpTopics("REJECTED", "requester").questions[0], "Why was my request rejected?");
});

test("courier help differs from requester help for the same status", () => {
  assert.notDeepEqual(orderHelpTopics("DELIVERED", "courier"), orderHelpTopics("DELIVERED", "requester"));
  assert.ok(orderHelpTopics("DELIVERED", "courier").questions.includes("When do I get paid for an errand?"));
});

test("unknown statuses still offer help", () => {
  assert.ok(orderHelpTopics("SOMETHING_NEW", "requester").questions.length > 0);
  assert.ok(orderHelpTopics("OPEN", "courier").questions.length > 0);
});

test("help context only describes the order locally", () => {
  const context = orderHelpContext({
    id: "812a77d9-d40b-408e-b106-a8d8695b34d6", supplierName: "Printers@PCCommons", status: "PICKED_UP",
    items: "2 printouts", deliveryLocation: "PGP House 5",
  }, "requester");
  assert.equal(context.title, "Printers@PCCommons · #812a77d9");
  assert.equal(context.statusLabel, "Picked up");
  assert.doesNotMatch(JSON.stringify(context), /printouts|PGP House/);
});

test("Help offers only the viewer's own unfinished requests and deliveries", () => {
  const me = "user-1";
  const orders = [
    { id: "a", requesterId: me, courierId: null, status: "OPEN" },
    { id: "b", requesterId: me, courierId: "user-2", status: "COMPLETED" },
    { id: "c", requesterId: "user-3", courierId: null, status: "OPEN" },
    { id: "d", requesterId: "user-4", courierId: me, status: "PICKED_UP" },
    { id: "e", requesterId: me, courierId: null, status: "REJECTED" },
  ];
  assert.deepEqual(helpOrderChoices(orders, me).map(({ order, role }) => [order.id, role]),
    [["a", "requester"], ["d", "courier"]]);
});

test("Help subscribers receive the latest published orders", () => {
  const seen = [];
  const unsubscribe = subscribeHelpOrders((list) => seen.push(list.length));
  publishHelpOrders([{ order: { id: "a" }, role: "requester" }]);
  unsubscribe();
  publishHelpOrders([]);
  assert.deepEqual(seen, [0, 1]);
});
