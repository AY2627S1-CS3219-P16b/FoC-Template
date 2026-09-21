import { sendAuthenticatedRequest } from "./client";

const API_BASE_URL = import.meta.env.VITE_USER_API_URL || "";

export async function registerUser(registration) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/users/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(registration),
    });
  } catch {
    throw new Error("The user service is unavailable. Please try again.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error("Registration failed.");
    error.fieldErrors = Object.fromEntries(
      (body.errors || []).map(({ field, message }) => [field, message]),
    );
    if (!body.errors?.length) {
      error.message = body.detail || "Registration failed. Please try again.";
    }
    throw error;
  }

  return body;
}

export async function loginUser(credentials) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/users/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
  } catch {
    throw new Error("The user service is unavailable. Please try again.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || "Login failed. Please try again.");
    if (body.errors?.length) {
      error.fieldErrors = Object.fromEntries(
        body.errors.map(({ field, message }) => [field, message]),
      );
    }
    throw error;
  }

  return body;
}

export function getUserProfile(token, userId) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}`, {
    token,
    method: "GET",
    errorMessage: "Could not load your profile.",
  });
}

export function updateUserProfile(token, userId, changes) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}`, {
    token,
    method: "PATCH",
    data: changes,
    errorMessage: "Could not save your profile.",
  });
}

export function updateUserRoleMode(token, userId, roleMode) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/role-mode`, {
    token,
    method: "PATCH",
    data: { active_role_mode: roleMode },
    errorMessage: "Could not change your role mode.",
  });
}

export function listUsers(token) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users`, {
    token,
    method: "GET",
    errorMessage: "Could not load user accounts.",
  });
}

export function listAdminAuditLogs(token, page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/admin/audit-logs?${params}`, {
    token,
    method: "GET",
    errorMessage: "Could not load audit history.",
  });
}

export function adminUpdateProfile(token, userId, changes, reason) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}`, {
    token,
    method: "PATCH",
    data: changes,
    headers: { "X-Admin-Reason": reason },
    errorMessage: "Could not update the account profile.",
  });
}

export function adminUpdateAuthRole(token, userId, authRole, reason) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/auth-role`, {
    token,
    method: "PATCH",
    data: { auth_role: authRole, reason },
    errorMessage: "Could not change the authorization role.",
  });
}

export function adminUpdateStatus(token, userId, accountStatus, reason) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}/status`, {
    token,
    method: "PATCH",
    data: { account_status: accountStatus, reason },
    errorMessage: "Could not change the account status.",
  });
}
