import React, { useEffect, useMemo, useState } from "react";
import {
  SUPPLIER_CATEGORIES,
  createPlace,
  createSupplier,
  deactivateSupplier,
  fetchPlaces,
  fetchSupplierAuditLogs,
  fetchSuppliers,
  formatPlace,
  updateSupplier,
} from "../api/suppliers";

const AUDIT_PAGE_SIZE = 10;
const LIST_PAGE_SIZE = 100;

const blankSupplier = {
  name: "",
  supplier_type: "FOOD_BEVERAGE",
  place_id: "",
  tags: "",
  floor: "",
  location_description: "",
  latitude: "",
  longitude: "",
  opening_time: "",
  closing_time: "",
  image_url: "",
  pickup_instructions: "",
};

/** The editable form for a supplier, or empty fields when adding one. */
function supplierForm(supplier) {
  if (!supplier) return { ...blankSupplier };
  return {
    name: supplier.name || "",
    supplier_type: supplier.supplier_type || "FOOD_BEVERAGE",
    place_id: supplier.place?.id || "",
    tags: (supplier.tags || []).join(", "),
    floor: supplier.floor || "",
    location_description: supplier.location_description || "",
    latitude: supplier.latitude ?? "",
    longitude: supplier.longitude ?? "",
    opening_time: (supplier.opening_time || "").slice(0, 5),
    closing_time: (supplier.closing_time || "").slice(0, 5),
    image_url: supplier.image_url || "",
    pickup_instructions: supplier.pickup_instructions || "",
  };
}

const splitTags = (value) => value.split(",").map((tag) => tag.trim()).filter(Boolean);

/** Mirrors the database's uniqueness key: lower(regexp_replace(name, …)). */
const nameKey = (value) => (value || "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Form labels, so the log reads in the same words as the form. */
const AUDIT_LABELS = {
  name: "Name",
  supplier_type: "Category",
  place_id: "Location",
  parent_id: "Inside",
  tags: "Tags",
  floor: "Floor",
  location_description: "Direction",
  opening_time: "Opens",
  closing_time: "Closes",
  image_url: "Image URL",
  pickup_instructions: "Pickup instructions",
  is_active: "Shown in browsing",
};

// Identifiers and derived columns the service sets; nobody chose them.
const AUDIT_INTERNAL = new Set(["id", "search_key"]);

const CATEGORY_LABELS = Object.fromEntries(
  SUPPLIER_CATEGORIES.map(({ value, label }) => [value, label]),
);

/** What happened and to what, as "Added location" plus "UTown". */
function auditTitle(entry, describe) {
  const subject = entry.new_value.name
    || describe(entry.entity_type === "PLACE" ? "parent_id" : "place_id", entry.entity_id)
    || "a record";
  const noun = entry.entity_type === "PLACE" ? "location" : "supplier";
  const actions = {
    PLACE_CREATED: "Added location",
    SUPPLIER_CREATED: "Added supplier",
    SUPPLIER_DEACTIVATED: "Hid supplier",
    SUPPLIER_UPDATED: entry.new_value.is_active === true
      ? "Restored supplier"
      : "Edited supplier",
  };
  return {
    action: actions[entry.action_type] || `Changed ${noun}`,
    subject,
  };
}

/** Marks a field the service refuses to accept empty. */
const Required = () => (
  <span className="required-marker" aria-label="required" title="Required"> *</span>
);

/**
 * What still stops this form being submitted, in the order the fields appear.
 * A disabled button with no explanation leaves the admin guessing which of ten
 * fields is at fault.
 */
function missingForSupplier({ form, reason, isNew, hasChanges }) {
  if (isNew) {
    const missing = [
      !form.name.trim() && "a name",
      !form.place_id && "a location",
      !(form.opening_time && form.closing_time) && "opening and closing times",
    ].filter(Boolean);
    return missing.length ? `Enter ${missing.join(", ")}.` : "";
  }
  // The reason gates Save and Hide alike, so say so: a disabled Hide button
  // with a message about saving explains the wrong control.
  if (!reason.trim()) return "Give a reason below to save or hide this supplier.";
  if (!hasChanges) return "Change a field before saving, or hide this supplier.";
  return "";
}

/** Form values as the API expects them: blank optional fields become null. */
function toPayload(form) {
  const blankToNull = (value) => (value.trim() ? value.trim() : null);
  const numberOrNull = (value) => (value === "" || value === null ? null : Number(value));
  return {
    name: form.name.trim(),
    supplier_type: form.supplier_type,
    place_id: form.place_id,
    tags: splitTags(form.tags),
    floor: blankToNull(form.floor),
    location_description: blankToNull(form.location_description),
    latitude: numberOrNull(form.latitude),
    longitude: numberOrNull(form.longitude),
    opening_time: blankToNull(form.opening_time),
    closing_time: blankToNull(form.closing_time),
    image_url: blankToNull(form.image_url),
    pickup_instructions: blankToNull(form.pickup_instructions),
  };
}

const sameValue = (a, b) =>
  Array.isArray(a) ? JSON.stringify(a) === JSON.stringify(b ?? []) : (a ?? null) === (b ?? null);

/** Only the fields that differ, so the audit entry shows the actual change. */
function changedFields(form, supplier) {
  const payload = toPayload(form);
  const current = toPayload(supplierForm(supplier));
  return Object.fromEntries(
    Object.entries(payload).filter(([field, value]) => !sameValue(value, current[field])),
  );
}

export default function SupplierAdminSection({ token }) {
  const [suppliers, setSuppliers] = useState([]);
  const [places, setPlaces] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState({ ...blankSupplier });
  // Only edits and deletions carry a reason; creating a record does not.
  const [reason, setReason] = useState("");
  const [filter, setFilter] = useState("");
  const [placeName, setPlaceName] = useState("");
  const [placeParent, setPlaceParent] = useState("");
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const selected = suppliers.find((supplier) => supplier.id === selectedId) || null;
  const isNew = selectedId === null;

  useEffect(() => {
    let active = true;
    // include_inactive so a hidden supplier can be found and restored.
    Promise.all([
      fetchSuppliers({ token, pageSize: LIST_PAGE_SIZE, includeInactive: true }),
      fetchPlaces({ token }),
    ])
      .then(([page, placeRows]) => {
        if (!active) return;
        setSuppliers(page.items);
        setPlaces(placeRows);
        setForbidden(false);
      })
      .catch((loadError) => {
        if (!active) return;
        if (loadError.status === 403) setForbidden(true);
        else setError(loadError.message);
      });
    return () => { active = false; };
  }, [token, refresh]);

  useEffect(() => {
    let active = true;
    fetchSupplierAuditLogs({ token, page: auditPage, pageSize: AUDIT_PAGE_SIZE })
      .then((result) => {
        if (!active) return;
        setAuditLogs(result.items);
        setAuditTotal(result.total);
        setForbidden(false);
      })
      .catch((loadError) => {
        if (!active) return;
        if (loadError.status === 403) setForbidden(true);
        // Otherwise say so: silence here once hid the log being fetched from
        // the wrong service, which answered 200 with an empty list.
        else setError(loadError.message);
      });
    return () => { active = false; };
  }, [token, auditPage, refresh]);

  const placeOptions = useMemo(() => places
    .map((place) => ({ ...place, label: formatPlace(place) }))
    .sort((a, b) => a.label.localeCompare(b.label, "en", { sensitivity: "base", numeric: true })),
  [places]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return suppliers.filter((supplier) => !needle
      || supplier.name.toLowerCase().includes(needle)
      || formatPlace(supplier.place).toLowerCase().includes(needle));
  }, [suppliers, filter]);

  const changes = selected ? changedFields(form, selected) : {};
  const hasChanges = isNew
    ? Boolean(form.name.trim() && form.place_id
      && form.opening_time && form.closing_time)
    : Object.keys(changes).length > 0;
  // The combination the unique index refuses, caught before the save so the
  // admin sees the cause rather than a 409. Must match the index expression:
  // capitals, spaces and punctuation are ignored when comparing names.
  const nameClash = suppliers.some((supplier) =>
    supplier.id !== selectedId
    && nameKey(supplier.name) === nameKey(form.name)
    && supplier.place?.id === form.place_id
    && (supplier.floor || "") === form.floor.trim());

  const supplierBlockedBy = missingForSupplier({ form, reason, isNew, hasChanges });
  const placeBlockedBy = placeName.trim() ? "" : "Enter a name.";

  // Stored values are ids, codes and flags. Resolve them against what is
  // already loaded so the log reads the way the form does.
  const names = useMemo(() => new Map([
    ...places.map((place) => [place.id, formatPlace(place)]),
    ...suppliers.map((supplier) => [supplier.id, supplier.name]),
  ]), [places, suppliers]);

  const describe = (field, value) => {
    if (field === "place_id" || field === "parent_id") {
      return value ? names.get(value) || "a location no longer listed" : "none";
    }
    if (value === null || value === undefined || value === "") return "not set";
    if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
    if (typeof value === "boolean") return value ? "yes" : "no";
    if (field === "supplier_type") return CATEGORY_LABELS[value] || value;
    if (field === "opening_time" || field === "closing_time") {
      return String(value).slice(0, 5);
    }
    return String(value);
  };

  const select = (supplier) => {
    setSelectedId(supplier?.id ?? null);
    setForm(supplierForm(supplier));
    setError("");
    setMessage("");
  };

  const done = (text) => {
    setMessage(text);
    setError("");
    setAuditPage(1);
    setRefresh((current) => current + 1);
  };

  const run = async (work, success) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      done(success);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setBusy(false);
    }
  };

  const save = (event) => {
    event.preventDefault();
    if (isNew) {
      return run(async () => {
        const created = await createSupplier({ token, supplier: toPayload(form) });
        setSelectedId(created.id);
      }, "Supplier created.");
    }
    return run(async () => {
      await updateSupplier({ token, supplierId: selected.id, changes, reason });
      setReason("");
    }, "Supplier saved.");
  };

  const toggleActive = () => {
    if (selected.is_active) {
      return run(async () => {
        await deactivateSupplier({ token, supplierId: selected.id, reason });
        setReason("");
      }, "Supplier hidden from browsing.");
    }
    return run(async () => {
      await updateSupplier({
        token, supplierId: selected.id, changes: { is_active: true }, reason,
      });
      setReason("");
    }, "Supplier restored.");
  };

  const addPlace = (event) => {
    event.preventDefault();
    return run(async () => {
      await createPlace({
        token,
        place: { name: placeName.trim(), parent_id: placeParent || null },
      });
      setPlaceName("");
      setPlaceParent("");
    }, "Location created.");
  };

  const field = (label, name, type = "text", wide = false, required = false, extra = {}) => (
    <div className={`form-group${wide ? " field-wide" : ""}`} key={name}>
      <label htmlFor={`supplier-${name}`}>
        {label}{required && <Required />}
      </label>
      <input
        id={`supplier-${name}`}
        type={type}
        value={form[name]}
        required={required}
        disabled={busy}
        onChange={(event) => setForm((current) => ({ ...current, [name]: event.target.value }))}
        {...extra}
      />
    </div>
  );

  if (forbidden) {
    return (
      <section>
        <div className="section-header"><h2>Supplier Records</h2></div>
        <div className="card">
          <p role="alert">
            Access denied. Supplier Service checked this account&rsquo;s current role and
            refused the request.
          </p>
          <p>
            <code>GET /api/v1/supplier-changes</code> &rarr; 403 Forbidden. Browsing
            suppliers still works, because reading only requires a signed-in account.
          </p>
        </div>
      </section>
    );
  }

  const auditPageCount = Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE));

  return (
    <section>
      <div className="section-header">
        <h2>Supplier Records</h2>
        <span className="section-count">{suppliers.length} total</span>
      </div>
      {error && <div className="action-error" role="alert">{error}</div>}
      {message && <div className="success-message" role="status">{message}</div>}

      <div className="supplier-admin-layout">
        <div className="card">
          <h3>Suppliers</h3>
          <div className="form-group">
            <input
              aria-label="Filter suppliers"
              placeholder="Filter by name or location…"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          <ul className="supplier-admin-list">
            {visible.map((supplier) => (
              <li key={supplier.id}>
                <button
                  type="button"
                  className={`btn btn-sm btn-block ${supplier.id === selectedId ? "btn-primary" : "btn-secondary"}${supplier.is_active ? "" : " is-hidden"}`}
                  onClick={() => select(supplier)}
                >
                  {supplier.name}
                  {!supplier.is_active && " (hidden)"}
                  <br />
                  <small>{formatPlace(supplier.place)}</small>
                </button>
              </li>
            ))}
            {visible.length === 0 && <li><small>No suppliers match that filter.</small></li>}
          </ul>
        </div>

        <div className="card">
          {/* The form owns the new/edit switch, so the list only selects. */}
          <div className="supplier-admin-form-header">
            <h3>{isNew ? "New supplier" : selected?.name}</h3>
            {!isNew && (
              <button type="button" className="btn btn-secondary btn-sm"
                      onClick={() => select(null)}>
                + New supplier
              </button>
            )}
          </div>
          {/* Up here rather than by the button: what is missing should be read
              before filling the form, not after scrolling past it. */}
          {supplierBlockedBy && <p className="form-hint">{supplierBlockedBy}</p>}
          <form onSubmit={save}>
            {/* Short fields pair up; .field-wide ones span both columns. */}
            <div className="supplier-admin-fields">
              <div className="form-group field-wide">
                <label htmlFor="supplier-name">Name<Required /></label>
                <input
                  id="supplier-name"
                  value={form.name}
                  required
                  disabled={busy}
                  onChange={(event) => setForm((c) => ({ ...c, name: event.target.value }))}
                />
                {/* A shared name is normal for a chain, so only the exact
                    name/location/floor clash is worth saying anything about. */}
                {nameClash && (
                  <div className="field-error">
                    This name is already used at that location and floor. Choose a
                    different location or floor.
                  </div>
                )}
              </div>
              <div className="form-group">
                <label htmlFor="supplier-type">Category<Required /></label>
                <select
                  id="supplier-type"
                  value={form.supplier_type}
                  disabled={busy}
                  onChange={(event) => setForm((c) => ({ ...c, supplier_type: event.target.value }))}
                >
                  {SUPPLIER_CATEGORIES.map((category) => (
                    <option key={category.value} value={category.value}>{category.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="supplier-floor">Floor</label>
                <input
                  id="supplier-floor"
                  value={form.floor}
                  disabled={busy}
                  placeholder="e.g. B1, G, 13"
                  pattern="[A-Za-z0-9]*"
                  title="Letters and digits only, e.g. B1, G, 13"
                  onChange={(event) => setForm((c) => ({ ...c, floor: event.target.value }))}
                />
              </div>
              <div className="form-group field-wide">
                <label htmlFor="supplier-place">Location<Required /></label>
                <select
                  id="supplier-place"
                  value={form.place_id}
                  disabled={busy}
                  onChange={(event) => setForm((c) => ({ ...c, place_id: event.target.value }))}
                >
                  <option value="">Select a location…</option>
                  {placeOptions.map((place) => (
                    <option key={place.id} value={place.id}>{place.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group field-wide">
                <label htmlFor="supplier-tags">Tags</label>
                <input
                  id="supplier-tags"
                  value={form.tags}
                  disabled={busy}
                  placeholder="coffee, halal"
                  onChange={(event) => setForm((c) => ({ ...c, tags: event.target.value }))}
                />
                <small>Comma separated. Stored lowercase.</small>
              </div>
              {field("Direction", "location_description", "text", true)}
              {/* Optional; the API rejects out-of-range values with 422, but
                  min/max/step catch a typo before that round trip. */}
              {field("Latitude", "latitude", "number", false, false,
                { min: -90, max: 90, step: "any", placeholder: "e.g. 1.2966" })}
              {field("Longitude", "longitude", "number", false, false,
                { min: -180, max: 180, step: "any", placeholder: "e.g. 103.7764" })}
              {field("Opens", "opening_time", "time", false, true)}
              {field("Closes", "closing_time", "time", false, true)}
              {field("Image URL", "image_url", "text", true)}
              {field("Pickup instructions", "pickup_instructions", "text", true)}
            </div>

            {/* Only when changing an existing record: a new one explains itself. */}
            {!isNew && (
              <div className="form-group">
                <label htmlFor="supplier-reason">Reason for this change<Required /></label>
                <input
                  id="supplier-reason"
                  value={reason}
                  disabled={busy}
                  placeholder="Recorded in the change history"
                  onChange={(event) => setReason(event.target.value)}
                />
              </div>
            )}

            <div className="form-actions">
              {/* Beside the buttons, not only at the top of the card: a
                  disabled button needs its explanation within sight. */}
              <p className="form-hint">
                {supplierBlockedBy || <><Required /> required</>}
              </p>
              {!isNew && selected && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={busy || !reason.trim()}
                  onClick={toggleActive}
                >
                  {selected.is_active ? "Hide from browsing" : "Restore"}
                </button>
              )}
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={busy || Boolean(supplierBlockedBy) || nameClash}
              >
                {isNew ? "Create supplier" : "Save changes"}
              </button>
            </div>
          </form>
        </div>

        <div className="card supplier-admin-aside">
          <h3>New location</h3>
          <p className="form-hint">
            A building, or a canteen or shop inside one.
          </p>
          {placeBlockedBy && <p className="form-hint">{placeBlockedBy}</p>}
          <form onSubmit={addPlace}>
            <div className="form-group">
              <label htmlFor="place-name">Name<Required /></label>
              <input
                id="place-name"
                value={placeName}
                disabled={busy}
                placeholder="e.g. The Deck"
                onChange={(event) => setPlaceName(event.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="place-parent">Inside (optional)</label>
              <select
                id="place-parent"
                value={placeParent}
                disabled={busy}
                onChange={(event) => setPlaceParent(event.target.value)}
              >
                <option value="">Not inside another location</option>
                {placeOptions.map((place) => (
                  <option key={place.id} value={place.id}>{place.label}</option>
                ))}
              </select>
              <small>
                Choose the building this sits in, so searching for the building
                also finds suppliers here.
              </small>
            </div>
            <p className="form-hint">
              A location cannot be removed once a supplier uses it.
            </p>
            <div className="form-actions">
              <p className="form-hint"><Required /> required</p>
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={busy || !placeName.trim()}
              >
                Create location
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="admin-divider" />
      {/* Named for its scope: User Service keeps its own log of account changes. */}
      <h3 className="audit-heading">Supplier changes</h3>
      {auditLogs.length === 0 && <p><small>No supplier changes recorded yet.</small></p>}
      {auditLogs.map((entry) => {
        const isCreate = entry.action_type.endsWith("_CREATED");
        const { action, subject } = auditTitle(entry, describe);
        return (
          <div className="audit-entry" key={entry.id}>
            <div className="audit-entry-header">
              <span><strong>{action}:</strong> {subject}</span>
              <span>{new Date(entry.created_at).toLocaleString()}</span>
            </div>
            {entry.reason && <div className="audit-reason">{entry.reason}</div>}
            {/* A create has nothing to compare against, so listing every field
                as "null → value" would say nothing the title does not. */}
            {!isCreate && (
              <div className="audit-changes">
                {Object.keys(entry.new_value)
                  .filter((key) => !AUDIT_INTERNAL.has(key))
                  .map((key) => (
                    <div className="audit-change" key={key}>
                      <span>{AUDIT_LABELS[key] || key.replace(/_/g, " ")}</span>
                      <span className="audit-change-values">
                        {describe(key, entry.previous_value[key])} &rarr;{" "}
                        {describe(key, entry.new_value[key])}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        );
      })}
      {auditPageCount > 1 && (
        <div className="audit-pagination">
          <button
            type="button"
            className="btn btn-sm"
            disabled={auditPage <= 1}
            onClick={() => setAuditPage((page) => page - 1)}
          >
            Previous
          </button>
          <span>Page {auditPage} of {auditPageCount}</span>
          <button
            type="button"
            className="btn btn-sm"
            disabled={auditPage >= auditPageCount}
            onClick={() => setAuditPage((page) => page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </section>
  );
}
