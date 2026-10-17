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

