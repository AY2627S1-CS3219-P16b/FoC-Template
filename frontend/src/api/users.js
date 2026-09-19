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

async function profileRequest(token, userId, method, changes) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/users/${encodeURIComponent(userId)}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(changes ? { "Content-Type": "application/json" } : {}),
      },
      ...(changes ? { body: JSON.stringify(changes) } : {}),
    });
  } catch {
    throw new Error("The user service is unavailable. Please try again.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || "Could not load your profile.");
    error.fieldErrors = Object.fromEntries(
      (body.errors || []).map(({ field, message }) => [field, message]),
    );
    throw error;
  }
  return body;
}

export function getUserProfile(token, userId) {
  return profileRequest(token, userId, "GET");
}

export function updateUserProfile(token, userId, changes) {
  return profileRequest(token, userId, "PATCH", changes);
}
