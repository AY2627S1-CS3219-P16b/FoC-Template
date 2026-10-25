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
  for (const name of ["OrderCard", "CourierOrdersSection", "RequesterOrdersSection", "CourierActiveSection", "Navbar"]) {
    components[name] = (await server.ssrLoadModule("/src/components/" + name + ".jsx")).default;
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
