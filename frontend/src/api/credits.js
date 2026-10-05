import { sendAuthenticatedRequest } from "./client";

const API_BASE_URL = import.meta.env.VITE_CREDIT_API_URL || "";

export function initializeCredits(token) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/credits/me/initialize`, {
    token,
    method: "POST",
    errorMessage: "Could not initialize credits.",
  });
}

export function getCredits(token) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/credits/me`, {
    token,
    method: "GET",
    errorMessage: "Could not load credits.",
  });
}

export function listCreditLedger(token, page = 1, pageSize = 20) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/credits/me/ledger?${params}`, {
    token,
    method: "GET",
    errorMessage: "Could not load credit ledger.",
  });
}

export function reserveCredits(token, orderId, amount = 1) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/credits/reservations`, {
    token,
    method: "POST",
    data: { order_id: orderId, amount },
    errorMessage: "Could not reserve credits.",
  });
}

export function releaseCredits(token, orderId) {
  return sendAuthenticatedRequest(
    `${API_BASE_URL}/api/v1/credits/reservations/${encodeURIComponent(orderId)}/release`,
    {
      token,
      method: "POST",
      errorMessage: "Could not release credits.",
    },
  );
}

export function transferCredits(token, orderId, courierUserId) {
  return sendAuthenticatedRequest(
    `${API_BASE_URL}/api/v1/credits/reservations/${encodeURIComponent(orderId)}/transfer`,
    {
      token,
      method: "POST",
      data: { courier_user_id: courierUserId },
      errorMessage: "Could not transfer credits.",
    },
  );
}
