export async function sendAuthenticatedRequest(url, { token, method, data, errorMessage }) {
  const headers = { Authorization: `Bearer ${token}` };
  if (data !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
    });
  } catch {
    throw new Error("The service is unavailable. Please try again.");
  }

  const responseBody = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(responseBody.detail || errorMessage);
    error.fieldErrors = Object.fromEntries(
      (responseBody.errors || []).map(({ field, message }) => [field, message]),
    );
    throw error;
  }
  return responseBody;
}
