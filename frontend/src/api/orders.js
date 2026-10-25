import { sendAuthenticatedRequest } from "./client";

const BASE_URL = `${import.meta.env.VITE_ORDER_API_URL || ""}/api/v1/orders`;

export function createOrder(token, body, key) {
  return sendAuthenticatedRequest(BASE_URL, {
    token, method: "POST", data: body, headers: { "Idempotency-Key": key },
    errorMessage: "Could not create this request.",
  });
}

export function getOrder(token, id) {
  return sendAuthenticatedRequest(`${BASE_URL}/${encodeURIComponent(id)}`, {
    token, method: "GET", errorMessage: "Could not load the order.",
  });
}

export function listAdminOrders(token, { page = 1, requesterId = "", status = "" } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (requesterId) params.set("requester_user_id", requesterId);
  if (status) params.set("status", status);
  return sendAuthenticatedRequest(`${BASE_URL}/admin?${params}`, {
    token, method: "GET", errorMessage: "Could not load admin orders.",
  });
}

async function listAll(token, path, filters) {
  const rows = [];
  for (let page = 1; ; page += 1) {
    const params = new URLSearchParams({ ...filters, page: String(page), page_size: "100" });
    const result = await sendAuthenticatedRequest(`${BASE_URL}${path}?${params}`, {
      token, method: "GET", errorMessage: "Could not load orders.",
    });
    rows.push(...result.items);
    if (page >= result.total_pages) return rows;
  }
}

export async function loadOrders(token) {
  const groups = await Promise.all([
    listAll(token, "", { status: "OPEN" }),
    listAll(token, "/me", { role: "requester" }),
    listAll(token, "/me", { role: "courier" }),
  ]);
  return [...new Map(groups.flat().map((order) => [order.id, order])).values()]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

export function changeOrder(token, id, action) {
  return sendAuthenticatedRequest(`${BASE_URL}/${encodeURIComponent(id)}/${action}`, {
    token, method: "POST", errorMessage: "Could not update this order.",
  });
}

export function orderForDisplay(order, userId) {
  return {
    id: order.id, supplierId: order.supplier_id, supplierName: order.supplier_name,
    pickupLocation: order.pickup_location, items: order.item_description,
    deliveryLocation: order.delivery_location, instructions: order.delivery_instructions || "None",
    creditsReward: order.credit_amount, status: order.status,
    requesterId: order.requester_user_id, courierId: order.courier_user_id,
    requesterName: order.requester_user_id === userId ? "You" : `Student ${order.requester_user_id.slice(0, 8)}`,
    courierName: order.courier_user_id ? (order.courier_user_id === userId ? "You" : "Assigned courier") : null,
    deadline: new Date(order.expires_at).toLocaleString(),
    createdAt: new Date(order.created_at).toLocaleString(),
    expiresAt: order.expires_at,
    createdAtIso: order.created_at,
    updatedAtIso: order.updated_at,
  };
}
