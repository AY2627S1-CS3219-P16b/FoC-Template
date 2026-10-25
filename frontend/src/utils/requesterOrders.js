const PAST_STATUSES = new Set(["COMPLETED", "CANCELLED", "EXPIRED", "REJECTED"]);

export const isActiveOrder = (order) => !PAST_STATUSES.has(order.status);

export function requesterPollDelay(view, orders) {
  if (view === "past" || (view === "all" && !orders.some(isActiveOrder))) return null;
  return orders.some((order) => ["RESERVING", "CANCELLING", "EXPIRING", "COMPLETING"].includes(order.status)) ? 1000 : 5000;
}
