import { sendAuthenticatedRequest } from "./client.js";

// Empty base URL keeps requests relative so the Vite proxy handles them in
// development. Set VITE_SUPPLIER_API_URL when the browser calls the service
// directly, which also requires CORS on the service.
const API_BASE_URL = import.meta.env?.VITE_SUPPLIER_API_URL || "";

export const SUPPLIER_CATEGORIES = [
  { value: "FOOD_BEVERAGE", label: "Food & Beverage" },
  { value: "RETAIL", label: "Retail" },
  { value: "FACILITY", label: "Facilities" },
];

// Values match the service's sort keys; "-" reverses.
export const SUPPLIER_SORTS = [
  { value: "name", label: "Name (A-Z)" },
  { value: "-name", label: "Name (Z-A)" },
  { value: "place", label: "Location (A-Z)" },
  { value: "category", label: "Category" },
];

export const DEFAULT_SORT = "name";

/** Retry only failures that may succeed without changing the request. */
export function canRetrySupplierRequest(error) {
  return error?.status === 0 || error?.status === 408 || error?.status === 429
    || (error?.status >= 500 && error?.status < 600);
}

/** Translate API failures into actions users can take; never display raw details. */
export function supplierErrorMessage(status, body = {}, context = "list") {
  if (status === 0) return "We couldn't connect. Check your connection and try again.";
  if (status === 401) return "Your session has expired or is no longer valid. Please log in again.";
  if (status === 403) return "You don't have permission to view this information.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return "Supplier information is temporarily unavailable. Please try again shortly.";
  if (status === 404) return context === "detail"
    ? "This supplier is no longer available. Return to the supplier list and choose another."
    : context === "places"
      ? "Locations are unavailable right now. Please try again."
      : "This location isn't available. Choose another location or clear the filters.";
  if (status === 422) {
    if (context === "detail") return "This supplier link isn't valid. Return to the supplier list and choose another.";
    const detail = body?.detail;
    const fields = Array.isArray(detail) ? detail.map((error) => error.loc?.at(-1)) : [];
    const text = typeof detail === "string" ? detail.toLowerCase() : "";
    if (fields.includes("type") || text.includes("supplier_type"))
      return "This category isn't available. Choose Food & Beverage, Retail or Facilities, or clear the filters.";
    if (fields.includes("sort") || text.includes("sort must"))
      return "This sorting option isn't available. Choose an option from the Sort menu.";
    if (fields.includes("page") || fields.includes("page_size"))
      return "This page link isn't valid. Clear the filters to return to the first page.";
    if (fields.includes("q")) return "Your search is too long. Please use 200 characters or fewer.";
    if (fields.includes("place") || text.includes("place name"))
      return "This location isn't valid. Choose a location from the list or clear the filters.";
    return "Some filters aren't valid. Clear the filters and try again.";
  }
  return context === "places"
    ? "We couldn't load locations. Please try again."
    : "We couldn't load supplier information. Please try again.";
}

/**
 * One page of suppliers.
 *
 * Filters are applied by the service, not in the browser, so paging stays
 * correct as the catalogue grows. Blank values are omitted so the service
 * sees no filter rather than an empty one.
 */
export async function fetchSuppliers({
  token,
  search,
  category,
  place,
  sort,
  page = 1,
  pageSize = 12,
  includeInactive = false,
} = {}) {
  const params = new URLSearchParams();
  if (search?.trim()) params.set("q", search.trim());
  if (category && category !== "ALL") params.set("type", category);
  if (place && place !== "ALL") params.set("place", place);
  if (sort && sort !== DEFAULT_SORT) params.set("sort", sort);
  if (includeInactive) params.set("include_inactive", "true");
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/suppliers?${params}`, {
    token,
    method: "GET",
    errorMessage: "Unable to load suppliers.",
    formatError: (status, body) => supplierErrorMessage(status, body, "list"),
  });
}

export async function fetchSupplier({ token, supplierId }) {
  return sendAuthenticatedRequest(
    `${API_BASE_URL}/api/v1/suppliers/${encodeURIComponent(supplierId)}`,
    { token, method: "GET", errorMessage: "Unable to load this supplier.",
      formatError: (status, body) => supplierErrorMessage(status, body, "detail") },
  );
}

/** Places for the location filter; children are returned with their parent. */
export async function fetchPlaces({ token }) {
  return sendAuthenticatedRequest(`${API_BASE_URL}/api/v1/places`, {
    token,
    method: "GET",
    errorMessage: "Unable to load campus locations.",
    formatError: (status, body) => supplierErrorMessage(status, body, "places"),
  });
}

/**
 * Admin writes, each recorded in the supplier service audit log.
 *
 * `reason` is sent only where the service requires it: changing or hiding a
 * record. Creating one carries no reason, so the header is omitted entirely.
 */
function adminRequest(url, { token, method, data, reason, action }) {
  return sendAuthenticatedRequest(`${API_BASE_URL}${url}`, {
    token,
    method,
    data,
    headers: reason === undefined ? undefined : { "X-Admin-Reason": reason },
    errorMessage: `Unable to ${action}.`,
    formatError: (status, body) => adminErrorMessage(status, body, action),
  });
}

/** Admin failures need the cause, since the admin can usually correct it. */
export function adminErrorMessage(status, body = {}, action = "save") {
  if (status === 0) return "We couldn't connect. Check your connection and try again.";
  if (status === 401) return "Your session has expired. Please log in again.";
  if (status === 403) return "Only administrators can change supplier records.";
  if (status === 404) return "That record no longer exists. Refresh and try again.";
  if (status === 409) return typeof body?.detail === "string" ? body.detail
    : "That change conflicts with an existing record.";
  if (status === 422) {
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const field = detail[0].loc?.at(-1);
      const msg = detail[0].msg;
      if (field === "X-Admin-Reason") return "Give a reason for this change.";
      // Pydantic's message is specific (e.g. what a valid floor looks like);
      // a generic "check the field" would throw that away.
      if (typeof msg === "string" && msg.startsWith("Value error, ")) {
        return msg.slice("Value error, ".length);
      }
      return `Check the ${String(field).replace(/_/g, " ")} field.`;
    }
    return "Some values aren't valid. Check the form and try again.";
  }
  if (status >= 500) return `Unable to ${action} right now. Please try again shortly.`;
  return `Unable to ${action}.`;
}

export function createSupplier({ token, supplier }) {
  return adminRequest("/api/v1/suppliers", {
    token, method: "POST", data: supplier, action: "create this supplier",
  });
}

export function updateSupplier({ token, supplierId, changes, reason }) {
  return adminRequest(`/api/v1/suppliers/${encodeURIComponent(supplierId)}`, {
    token, method: "PATCH", data: changes, reason, action: "save this supplier",
  });
}

/** Hides a supplier from browsing; the record stays so orders still resolve. */
export function deactivateSupplier({ token, supplierId, reason }) {
  return adminRequest(`/api/v1/suppliers/${encodeURIComponent(supplierId)}`, {
    token, method: "DELETE", reason, action: "hide this supplier",
  });
}

export function createPlace({ token, place }) {
  return adminRequest("/api/v1/places", {
    token, method: "POST", data: place, action: "create this location",
  });
}

export function fetchSupplierAuditLogs({ token, page = 1, pageSize = 10 }) {
  return sendAuthenticatedRequest(
    `${API_BASE_URL}/api/v1/supplier-changes?page=${page}&page_size=${pageSize}`,
    { token, method: "GET", errorMessage: "Unable to load the change history.",
      formatError: (status, body) => adminErrorMessage(status, body, "load the change history") },
  );
}

/** Formats a supplier's place for display, e.g. "Frontier (LT27)". */
export function formatPlace(place) {
  if (!place) return "";
  return place.parent_name ? `${place.name} (${place.parent_name})` : place.name;
}

/**
 * Stored times as "09:30 - 19:30".
 *
 * 00:00 to 23:59 is how a supplier that never closes is stored, so it reads as
 * "Open 24 hours" rather than as a range covering all but one minute.
 */
export function formatHours(supplier) {
  const trim = (value) => (value ? value.slice(0, 5) : null);
  const opening = trim(supplier.opening_time);
  const closing = trim(supplier.closing_time);
  if (!opening || !closing) return "";
  if (opening === "00:00" && closing === "23:59") return "Open 24 hours";
  return `${opening} - ${closing}`;
}
