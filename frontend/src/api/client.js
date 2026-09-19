// `headers` is optional and holds endpoint-specific headers, such as an admin reason.
export async function sendAuthenticatedRequest(url, { token, method, data, errorMessage, headers }) {
  const requestHeaders = { ...(headers ?? {}), Authorization: `Bearer ${token}` };
  if (data !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: requestHeaders,
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
