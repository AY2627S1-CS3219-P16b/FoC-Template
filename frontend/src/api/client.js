import {
  SESSION_EXPIRED_MESSAGE,
  endExpiredSession,
  getAccessToken,
  refreshAccessToken,
} from "./session.js";

// `headers` is optional and holds endpoint-specific headers, such as an admin reason.
export async function sendAuthenticatedRequest(url, { token, method, data, errorMessage, headers, formatError }) {
  // Prefer the stored token: it may have been refreshed since the caller read it.
  let currentToken = getAccessToken() || token;
  let response = await send(url, { token: currentToken, method, data, headers, formatError });

  // An expired access token is renewed once, then the request is retried.
  if (response.status === 401) {
    let refreshedToken;
    try {
      refreshedToken = await refreshAccessToken();
    } catch {
      throw unavailableError(formatError);
    }
    if (!refreshedToken) {
      endExpiredSession();
      throw sessionExpiredError();
    }
    currentToken = refreshedToken;
    response = await send(url, { token: currentToken, method, data, headers, formatError });
    if (response.status === 401) {
      endExpiredSession();
      throw sessionExpiredError();
    }
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

async function send(url, { token, method, data, headers, formatError }) {
  const requestHeaders = { ...(headers ?? {}), Authorization: `Bearer ${token}` };
  // A file upload is sent as-is: the browser sets the multipart boundary itself.
  const isForm = data instanceof FormData;
  if (data !== undefined && !isForm) {
    requestHeaders["Content-Type"] = "application/json";
  }
  try {
    return await fetch(url, {
      method,
      headers: requestHeaders,
      ...(data !== undefined ? { body: isForm ? data : JSON.stringify(data) } : {}),
    });
  } catch {
    throw unavailableError(formatError);
  }
}

function unavailableError(formatError) {
  const error = new Error(formatError ? formatError(0, {}) : "The service is unavailable. Please try again.");
  error.status = 0;
  return error;
}

function sessionExpiredError() {
  const error = new Error(SESSION_EXPIRED_MESSAGE);
  error.status = 401;
  error.sessionExpired = true;
  return error;
}
