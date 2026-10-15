// `headers` is optional and holds endpoint-specific headers, such as an admin reason.
export async function sendAuthenticatedRequest(url, { token, method, data, errorMessage, headers, formatError }) {
  const requestHeaders = { ...(headers ?? {}), Authorization: `Bearer ${token}` };
  // A file upload is sent as-is: the browser sets the multipart boundary itself.
  const isForm = data instanceof FormData;
  if (data !== undefined && !isForm) {
    requestHeaders["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: requestHeaders,
      ...(data !== undefined ? { body: isForm ? data : JSON.stringify(data) } : {}),
    });
  } catch {
    const error = new Error(formatError ? formatError(0, {}) : "The service is unavailable. Please try again.");
    error.status = 0;
    throw error;
  }

  const responseBody = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(formatError
      ? formatError(response.status, responseBody)
      : (typeof responseBody.detail === "string" ? responseBody.detail : errorMessage));
    error.status = response.status;
    error.fieldErrors = Object.fromEntries(
      (responseBody.errors || []).map(({ field, message }) => [field, message]),
    );
    throw error;
  }
  return responseBody;
}
