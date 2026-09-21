import React, { useEffect, useState } from "react";
import {
  adminUpdateAuthRole,
  adminUpdateProfile,
  adminUpdateStatus,
  listAdminAuditLogs,
  listUsers,
} from "../api/users";

function profileForm(user) {
  return {
    display_name: user?.display_name || "",
    contact_preference: user?.contact_preference || "",
    telegram_handle: user?.telegram_handle || "",
    phone_number: user?.phone_number || "",
    profile_picture_url: user?.profile_picture_url || "",
  };
}

const AUDIT_PAGE_SIZE = 10;

const auditFieldLabels = {
  display_name: "Display name",
  contact_preference: "Contact preference",
  telegram_handle: "Telegram handle",
  phone_number: "Phone number",
  profile_picture_url: "Profile picture URL",
  auth_role: "Authorization role",
  account_status: "Account status",
};

function auditValue(value) {
  return value === null || value === undefined || value === "" ? "Not set" : String(value);
}

export default function AdminSection({ token, currentUserId }) {
  const [accounts, setAccounts] = useState([]);
  const [endpointResults, setEndpointResults] = useState({ accounts: null, audit: null });
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditError, setAuditError] = useState("");
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditRefresh, setAuditRefresh] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(profileForm(null));
  const [nextRole, setNextRole] = useState("USER");
  const [nextStatus, setNextStatus] = useState("ACTIVE");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const selected = accounts.find((account) => account.id === selectedId);
  const profileChanges = selected ? Object.fromEntries(
    Object.entries(form).filter(([name, value]) => value !== (selected[name] ?? "")),
  ) : {};
  const hasChanges = selected && (
    Object.keys(profileChanges).length > 0 ||
    nextRole !== selected.auth_role ||
    nextStatus !== selected.account_status
  );
  const auditPageCount = Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE));

  useEffect(() => {
    let active = true;
    listUsers(token)
      .then((users) => {
        if (!active) return;
        setEndpointResults((current) => ({ ...current, accounts: 200 }));
        setAccounts(users);
        setSelectedId(users.find((user) => user.id !== currentUserId)?.id || users[0]?.id || null);
      })
      .catch((loadError) => {
        if (!active) return;
        setEndpointResults((current) => ({ ...current, accounts: loadError.status || "error" }));
        setAccounts([]);
        setSelectedId(null);
        if (loadError.status !== 403) setError(loadError.message);
      });
    return () => { active = false; };
  }, [token, currentUserId]);

  useEffect(() => {
    let active = true;
    setAuditLoading(true);
    setAuditError("");
    listAdminAuditLogs(token, auditPage, AUDIT_PAGE_SIZE)
      .then((result) => {
        if (!active) return;
        setEndpointResults((current) => ({ ...current, audit: 200 }));
        setAuditLogs(result.items);
        setAuditTotal(result.total);
      })
      .catch((loadError) => {
        if (!active) return;
        setEndpointResults((current) => ({ ...current, audit: loadError.status || "error" }));
        setAuditLogs([]);
        setAuditTotal(0);
        setAuditError(loadError.message);
      })
      .finally(() => {
        if (active) setAuditLoading(false);
      });
    return () => { active = false; };
  }, [token, auditPage, auditRefresh]);

  useEffect(() => {
    setForm(profileForm(selected));
    setNextRole(selected?.auth_role || "USER");
    setNextStatus(selected?.account_status || "ACTIVE");
  }, [selected]);

  const saveChanges = async (event) => {
    event.preventDefault();
    if (!selected || selected.id === currentUserId) return;
    if (!hasChanges) return;
    if (!reason.trim()) {
      setError("Enter a reason before changing this account.");
      setFieldErrors({ reason: "A reason is required for every admin change." });
      setMessage("");
      return;
    }
    setBusy(true);
    setError("");
    setFieldErrors({});
    setMessage("");
    let updated = selected;
    let completed = 0;
    try {
      if (Object.keys(profileChanges).length > 0) {
        updated = await adminUpdateProfile(token, selected.id, profileChanges, reason);
        completed += 1;
      }
      if (nextRole !== selected.auth_role) {
        updated = await adminUpdateAuthRole(token, selected.id, nextRole, reason);
        completed += 1;
      }
      if (nextStatus !== selected.account_status) {
        updated = await adminUpdateStatus(token, selected.id, nextStatus, reason);
        completed += 1;
      }
      setAccounts((current) => current.map((account) => account.id === updated.id ? updated : account));
      setReason("");
      setMessage("Account changes saved.");
    } catch (changeError) {
      if (completed > 0) {
        setAccounts((current) => current.map((account) => account.id === updated.id ? updated : account));
      }
      setFieldErrors(changeError.fieldErrors || {});
      setError(completed > 0 ? `Some changes were saved. ${changeError.message}` : changeError.message);
    } finally {
      if (completed > 0) {
        setAuditPage(1);
        setAuditRefresh((current) => current + 1);
      }
      setBusy(false);
    }
  };

  const input = (label, name) => (
    <div className="form-group">
      <label htmlFor={`admin-${name}`}>{label}</label>
      <input
        id={`admin-${name}`}
        value={form[name]}
        disabled={busy}
        onChange={(event) => setForm((current) => ({ ...current, [name]: event.target.value }))}
      />
      {fieldErrors[name] && <div className="field-error">{fieldErrors[name]}</div>}
    </div>
  );

  if (endpointResults.accounts === 403 || endpointResults.audit === 403) {
    const resultLabel = (status) => status === null ? "Checking…" : status === 403 ? "403 Forbidden" : String(status);
    return (
      <section>
        <div className="section-header"><h2>Admin access</h2></div>
        <div className="card">
          <p role="alert">Access denied. This account does not currently have admin permission.</p>
          <p>The User Service checked the account’s current role when these requests arrived:</p>
          <ul>
            <li><code>GET /api/v1/users</code> → {resultLabel(endpointResults.accounts)}</li>
            <li><code>GET /api/v1/admin/audit-logs</code> → {resultLabel(endpointResults.audit)}</li>
          </ul>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="section-header"><h2>Admin Accounts</h2></div>
      {error && <div className="action-error" role="alert">{error}</div>}
      {message && <div className="success-message" role="status">{message}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "12px" }}>
        <div className="card">
          <h3>Accounts</h3>
          {accounts.map((account) => (
            <button
              key={account.id}
              type="button"
              disabled={busy}
              className={`btn ${selectedId === account.id ? "btn-primary" : "btn-secondary"} btn-sm`}
              style={{ display: "block", marginBottom: "8px", textAlign: "left", width: "100%" }}
              onClick={() => { setSelectedId(account.id); setError(""); setMessage(""); }}
            >
              {account.display_name} · {account.email}<br />
              {account.auth_role} · {account.account_status}
            </button>
          ))}
        </div>
        {selected && (
          <div className="card">
            <h3>{selected.display_name}</h3>
            <p><strong>User ID:</strong> {selected.id}</p>
            <p><strong>Email:</strong> {selected.email}</p>
            <p><strong>Active mode:</strong> {selected.active_role_mode}</p>
            {selected.id === currentUserId ? (
              <p>Use the Profile tab to edit your own account.</p>
            ) : (
              <form onSubmit={saveChanges}>
                <hr className="admin-divider" />
                <h4>Profile</h4>
                {input("Display name", "display_name")}
                <div className="form-group">
                  <label htmlFor="admin-contact">Contact preference</label>
                  <select id="admin-contact" value={form.contact_preference} disabled={busy} onChange={(event) => setForm((current) => ({ ...current, contact_preference: event.target.value }))}>
                    <option value="">None</option><option value="EMAIL">Email</option><option value="TELEGRAM">Telegram</option><option value="PHONE">Phone</option>
                  </select>
                </div>
                {input("Telegram handle", "telegram_handle")}
                {input("Phone number", "phone_number")}
                {input("Profile picture URL", "profile_picture_url")}
                <hr className="admin-divider" />
                <div className="form-group">
                  <label htmlFor="admin-role">Authorization role</label>
                  <select id="admin-role" value={nextRole} disabled={busy} onChange={(event) => setNextRole(event.target.value)}>
                    <option value="USER">USER</option><option value="ADMIN">ADMIN</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="admin-status">Account status</label>
                  <select id="admin-status" value={nextStatus} disabled={busy} onChange={(event) => setNextStatus(event.target.value)}>
                    <option value="ACTIVE">ACTIVE</option><option value="SUSPENDED">SUSPENDED</option><option value="DISABLED">DISABLED</option>
                  </select>
                </div>
                <hr className="admin-divider" />
                <div className="form-group">
                  <label htmlFor="admin-reason">Reason for this admin change (required)</label>
                  <input id="admin-reason" value={reason} disabled={busy} onChange={(event) => { setReason(event.target.value); setFieldErrors((current) => ({ ...current, reason: undefined })); }} maxLength={500} />
                  {fieldErrors.reason && <div className="field-error">{fieldErrors.reason}</div>}
                </div>
                <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !hasChanges}>{busy ? "Saving..." : "Save changes"}</button>
              </form>
            )}
          </div>
        )}
      </div>
      <div className="card" style={{ marginTop: "12px" }}>
        <div className="audit-heading">
          <h3>Audit history</h3>
          {!auditLoading && !auditError && <span>{auditTotal} {auditTotal === 1 ? "change" : "changes"}</span>}
        </div>
        {auditError && <div className="action-error" role="alert">{auditError}</div>}
        {auditLoading && <p>Loading audit history...</p>}
        {!auditLoading && !auditError && auditLogs.length === 0 && <p>No admin changes recorded.</p>}
        {!auditLoading && !auditError && auditLogs.map((entry) => (
          <article className="audit-entry" key={entry.id}>
            <div className="audit-entry-header">
              <strong>{entry.action_type === "PROFILE_UPDATED" ? "Profile updated" : entry.action_type === "AUTH_ROLE_CHANGED" ? "Authorization role changed" : "Account status changed"}</strong>
              <time dateTime={entry.timestamp}>{new Date(entry.timestamp).toLocaleString()}</time>
            </div>
            <div className="audit-people">
              <div>
                <h4>Admin</h4>
                <dl>
                  <div><dt>Display name</dt><dd>{entry.acting_admin_display_name}</dd></div>
                  <div><dt>Email</dt><dd>{entry.acting_admin_email}</dd></div>
                </dl>
              </div>
              <div>
                <h4>Target Account</h4>
                <dl>
                  <div><dt>Display name</dt><dd>{entry.target_display_name}</dd></div>
                  <div><dt>Email</dt><dd>{entry.target_email}</dd></div>
                </dl>
              </div>
            </div>
            <div className="audit-changes">
              {Object.entries(entry.new_value).map(([field, value]) => (
                <div className="audit-change" key={field}>
                  <p><strong>Changed field:</strong> {auditFieldLabels[field] || field}</p>
                  <p className="audit-change-values">{auditValue(entry.previous_value[field])} → {auditValue(value)}</p>
                </div>
              ))}
            </div>
            <p className="audit-reason"><strong>Reason:</strong> {entry.reason}</p>
          </article>
        ))}
        {!auditLoading && !auditError && auditTotal > AUDIT_PAGE_SIZE && (
          <nav className="audit-pagination" aria-label="Audit history pages">
            <button className="btn btn-secondary btn-sm" type="button" disabled={auditPage === 1} onClick={() => setAuditPage((page) => page - 1)}>Previous</button>
            <span>Page {auditPage} of {auditPageCount}</span>
            <button className="btn btn-secondary btn-sm" type="button" disabled={auditPage >= auditPageCount} onClick={() => setAuditPage((page) => page + 1)}>Next</button>
          </nav>
        )}
      </div>
    </section>
  );
}
