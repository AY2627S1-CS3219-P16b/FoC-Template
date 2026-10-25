export const ORDER_STATUS_LABELS = {
  RESERVING: "Reserving credits", OPEN: "Open", ACCEPTED: "Accepted",
  PICKED_UP: "Picked up", DELIVERED: "Delivered", COMPLETING: "Processing reward",
  COMPLETED: "Completed", CANCELLING: "Cancelling", CANCELLED: "Cancelled",
  EXPIRING: "Expiring", EXPIRED: "Expired", REJECTED: "Rejected",
};

export const statusLabel = (status) => ORDER_STATUS_LABELS[status]
  || String(status || "Unknown").replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase());

export function statusTone(status) {
  if (status === "OPEN") return "open";
  if (["RESERVING", "ACCEPTED", "CANCELLING", "EXPIRING", "COMPLETING"].includes(status)) return "pending";
  if (status === "PICKED_UP") return "progress";
  if (["DELIVERED", "COMPLETED"].includes(status)) return "success";
  if (status === "REJECTED") return "danger";
  return "neutral";
}

export const shortOrderId = (id) => String(id || "").slice(0, 8);
export const creditLabel = (amount) => `${amount ?? 0} ${Number(amount) === 1 ? "credit" : "credits"}`;

export function formatOrderDate(value, { detailed = false } = {}) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-SG", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    hourCycle: "h23", timeZone: "Asia/Singapore",
    ...(detailed ? { year: "numeric", second: "2-digit" } : {}),
  }).format(date);
}

export function acceptanceDeadline(value, now = Date.now()) {
  const remaining = new Date(value).getTime() - now;
  if (!value || !Number.isFinite(remaining)) return "Deadline unavailable";
  if (remaining <= 0) return "Acceptance closed";
  const minutes = Math.ceil(remaining / 60000);
  if (minutes < 60) return `Accept within ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `Accept within ${hours} hr${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
}
