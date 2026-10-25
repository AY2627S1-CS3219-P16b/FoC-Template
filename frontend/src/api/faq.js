const API_BASE_URL = import.meta.env?.VITE_FAQ_API_URL || "";

export async function askFaq(question, { signal } = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, 60000);
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/faq/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = response.status === 429
        ? "Support is busy. Please wait a minute before trying again."
        : [413, 422].includes(response.status)
          ? "Please enter a question of up to 1,500 characters."
          : "Help is unavailable right now. Please try again in a moment.";
      const error = new Error(message);
      error.status = response.status;
      // Only accept server-generated UUIDs, never arbitrary backend error text.
      if (/^[0-9a-f-]{36}$/.test(body.request_id || "")) error.requestId = body.request_id;
      throw error;
    }
    if (typeof body.answer !== "string" || !["answered", "not_found"].includes(body.status)
        || !Array.isArray(body.sources)) {
      throw new Error("Support returned an incomplete answer. Please try again.");
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError" && signal?.aborted) throw error;
    if (controller.signal.aborted) throw new Error("Support took too long to respond. Please try again.");
    if (error instanceof TypeError) throw new Error("Could not reach support. Check your connection and try again.");
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
