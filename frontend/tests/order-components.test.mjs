import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { createServer as createHttpServer } from "node:http";

let server;
const components = {};
before(async () => {
  // Attach Vite's optional HMR transport to an unlistened server: rendering
  // tests need no network socket or browser server.
  server = await createServer({ configFile: false, plugins: [react()], logLevel: "error", server: { middlewareMode: true, hmr: { server: createHttpServer() }, watch: null }, appType: "custom", optimizeDeps: { noDiscovery: true } });
  for (const name of ["OrderCard", "OrderActionButton", "CourierOrdersSection", "RequesterOrdersSection", "CourierActiveSection", "Navbar"]) {
    const module = await server.ssrLoadModule("/src/components/" + name + ".jsx");
    components[name] = name === "RequesterOrdersSection" ? module.RequesterOrdersView : module.default;
  }
});
after(async () => { await server?.close(); });
const render = (name, props) => renderToStaticMarkup(React.createElement(components[name], props));
const noop = () => {};
const order = {
  id: "812a77d9-d40b-408e-b106-a8d8695b34d6", supplierName: "A Hot Hideout", items: "Mala, less spicy",
  pickupLocation: "Prince George's Park, Level 2", deliveryLocation: "Raffles Hall",
  requesterId: "requester-1", requesterName: "Student 12345678", courierName: null,
  creditsReward: 1, status: "OPEN", instructions: "Meet at the lobby",
  expiresAt: "2026-10-25T08:57:05Z", createdAtIso: "2026-10-25T08:12:05Z",
};

test("order headings show the supplier, with full identifiers and instructions retained in details", () => {
  const html = render("OrderCard", { order });
  assert.match(html, /<h3>A Hot Hideout<\/h3>/);
  assert.doesNotMatch(html, /<h3>[^<]*812a77d9/);
  assert.match(html, /<code>812a77d9-d40b-408e-b106-a8d8695b34d6<\/code>/);
  assert.match(html, /Meet at the lobby/);
  assert.match(html, /<summary>View details<\/summary>/);
  assert.match(html, /1 credit/);
});

test("couriers cannot accept their own orders or accept while already assigned", () => {
  const own = render("CourierOrdersSection", { orders: [order], currentUserId: order.requesterId, onAcceptOrder: noop, hasActiveTask: false });
  assert.match(own, /Your own request/);
  assert.doesNotMatch(own, />Accept Order/);
  const busy = render("CourierOrdersSection", { orders: [order], currentUserId: "someone-else", onAcceptOrder: noop, hasActiveTask: true });
  assert.match(busy, /disabled=""[^>]*>Active assignment in progress/);
  assert.doesNotMatch(busy, />Accept Order/);
});

test("requester controls remain tied to valid lifecycle states", () => {
  const props = { onCancelOrder: noop, onConfirmDelivery: noop, onNewRequestClick: noop };
  assert.match(render("RequesterOrdersSection", { ...props, orders: [order] }), /Cancel Request/);
  const accepted = render("RequesterOrdersSection", { ...props, orders: [{ ...order, status: "ACCEPTED" }] });
  assert.doesNotMatch(accepted, /Cancel Request|Confirm Delivery/);
  assert.match(render("RequesterOrdersSection", { ...props, orders: [{ ...order, status: "DELIVERED" }] }), /Confirm Delivery/);
  assert.match(render("RequesterOrdersSection", { ...props, orders: [{ ...order, status: "COMPLETING" }] }), /Credit processing is pending/);
});

test("active assignment controls advance one stage at a time", () => {
  const props = { onMarkPickedUp: noop, onMarkDelivered: noop, onFindNewTask: noop };
  const accepted = render("CourierActiveSection", { ...props, activeTask: { ...order, status: "ACCEPTED" } });
  assert.match(accepted, /Mark Picked Up/);
  assert.doesNotMatch(accepted, /Mark Delivered/);
  const picked = render("CourierActiveSection", { ...props, activeTask: { ...order, status: "PICKED_UP" } });
  assert.match(picked, /Mark Delivered/);
  assert.doesNotMatch(picked, /Mark Picked Up/);
  assert.match(render("CourierActiveSection", { ...props, activeTask: null }), /Browse Open Orders/);
});

test("navigation adapts to mode and only offers admin access to admins", () => {
  const props = { role: "REQUESTER", activeTab: "suppliers", user: { name: "Student", authRole: "USER" }, availableCredits: 20, setRole: noop, setActiveTab: noop, onLogout: noop };
  const requester = render("Navbar", props);
  assert.match(requester, /Suppliers/);
  assert.match(requester, /My Requests/);
  assert.match(requester, /20 available credits/);
  assert.doesNotMatch(requester, /Admin Access|Open Orders/);
  const admin = render("Navbar", { ...props, role: "COURIER", user: { name: "Admin", authRole: "ADMIN" } });
  assert.match(admin, /Open Orders/);
  assert.match(admin, /Active Assignment/);
  assert.match(admin, /Admin Access/);
});

test("pending order buttons show progress and become usable again when the action finishes", () => {
  for (const [action, label] of [["accept", "Accepting…"], ["cancel", "Cancelling…"], ["confirm", "Confirming…"], ["pickup", "Updating…"], ["deliver", "Updating…"]]) {
    const pending = render("OrderActionButton", { action, pendingAction: action, onClick: noop });
    assert.match(pending, /disabled=""/);
    assert.match(pending, /aria-busy="true"/);
    assert.ok(pending.includes(label));
    const finished = render("OrderActionButton", { action, onClick: noop });
    assert.doesNotMatch(finished, /disabled=""|aria-busy="true"/);
    assert.ok(!finished.includes(label));
  }
  // Polling can advance the order's status before its original request returns.
  // The next action must remain disabled until that request has finished.
  const nextAction = render("OrderActionButton", { action: "deliver", pendingAction: "pickup", onClick: noop });
  assert.match(nextAction, /disabled=""/);
  assert.match(nextAction, /Mark Delivered/);
});

test("progress is tied to the matching order across requester, courier and active assignment views", () => {
  const other = { ...order, id: "another-order" };
  const pendingOrderActions = { [order.id]: "accept" };
  const courier = render("CourierOrdersSection", { orders: [order, other], currentUserId: "courier-1", onAcceptOrder: noop, hasActiveTask: false, pendingOrderActions });
  assert.equal((courier.match(/disabled=""/g) || []).length, 1);
  assert.match(courier, /Accepting…/);
  assert.match(courier, /Accept Order/);

  const requesterProps = { onCancelOrder: noop, onConfirmDelivery: noop, onNewRequestClick: noop };
  const requester = render("RequesterOrdersSection", { ...requesterProps, orders: [order, { ...other, status: "DELIVERED" }], pendingOrderActions: { [order.id]: "cancel", [other.id]: "confirm" } });
  assert.equal((requester.match(/aria-busy="true"/g) || []).length, 2);
  assert.match(requester, /Cancelling…/);
  assert.match(requester, /Confirming…/);

  for (const [status, action] of [["ACCEPTED", "pickup"], ["PICKED_UP", "deliver"]]) {
    const active = render("CourierActiveSection", { activeTask: { ...order, status }, pendingAction: action, onMarkPickedUp: noop, onMarkDelivered: noop, onFindNewTask: noop });
    assert.match(active, /disabled="" aria-busy="true"[^>]*>Updating…/);
  }
});

test("request views show the selected filter, server totals and bounded pagination", () => {
  const props = { orders: [order], onNewRequestClick: noop, onCancelOrder: noop, onConfirmDelivery: noop, onViewChange: noop, onPageChange: noop, onRefresh: noop, view: "past", total: 24, totalPages: 3 };
  const first = render("RequesterOrdersSection", { ...props, page: 1 });
  assert.match(first, /aria-pressed="true"[^>]*>Past/);
  assert.match(first, /aria-pressed="false"[^>]*>Active/);
  assert.doesNotMatch(first, /<button[^>]*>All<\/button>/);
  assert.match(first, /24 past requests/);
  assert.match(first, /Page 1 of 3/);
  assert.match(first, /disabled=""[^>]*>Previous/);
  assert.doesNotMatch(first, /disabled=""[^>]*>Next/);
  const last = render("RequesterOrdersSection", { ...props, page: 3 });
  assert.match(last, /disabled=""[^>]*>Next/);
  assert.doesNotMatch(last, /disabled=""[^>]*>Previous/);
  const empty = render("RequesterOrdersSection", { ...props, orders: [], total: 0, totalPages: 0 });
  assert.match(empty, /No past requests/);
  assert.doesNotMatch(empty, /My request pages|Browse Suppliers/);
  const loading = render("RequesterOrdersSection", { ...props, hasResult: false, loading: true });
  assert.match(loading, /Loading requests…/);
  assert.doesNotMatch(loading, /No past requests|24 past requests|Page 1 of 3/);
  const failed = render("RequesterOrdersSection", { ...props, hasResult: false, error: "Could not load your requests." });
  assert.match(failed, /role="alert"[^>]*>Could not load your requests/);
  assert.doesNotMatch(failed, /No past requests|24 past requests/);
});
