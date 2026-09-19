import React, { useEffect, useState } from "react";

export default function ProfileSection({
  user,
  onUpdateUser,
  loadError,
  role,
  setRole,
  switchingRole,
  availableCredits,
}) {
  const [form, setForm] = useState({
    display_name: user.name || "",
    contact_preference: user.contactPreference || "",
    telegram_handle: user.telegram || "",
    phone_number: user.phoneNumber || "",
    profile_picture_url: user.profilePictureUrl || "",
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [actionError, setActionError] = useState("");
  const [savedMsg, setSavedMsg] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm({
      display_name: user.name || "",
      contact_preference: user.contactPreference || "",
      telegram_handle: user.telegram || "",
      phone_number: user.phoneNumber || "",
      profile_picture_url: user.profilePictureUrl || "",
    });
  }, [user]);

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setSavedMsg(false);
    setActionError("");
    setFieldErrors({});
    try {
      await onUpdateUser(form);
      setSavedMsg(true);
    } catch (error) {
      setFieldErrors(error.fieldErrors || {});
      if (!Object.keys(error.fieldErrors || {}).length)
        setActionError(error.message);
    } finally {
      setSaving(false);
    }
  };

  const field = (label, name, type = "text") => (
    <div className="form-group">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        type={type}
        value={form[name]}
        onChange={(event) => setForm({ ...form, [name]: event.target.value })}
      />
      {fieldErrors[name] && (
        <div className="field-error">{fieldErrors[name]}</div>
      )}
    </div>
  );

  return (
    <section>
      <div className="section-header">
        <h2>User Profile</h2>
      </div>
      {loadError && (
        <div className="action-error" role="alert">
          {loadError}
        </div>
      )}
      {savedMsg && (
        <div
          className="notice-box"
          role="status"
          style={{ borderColor: "#16A34A", color: "#16A34A" }}
        >
          Profile saved.
        </div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "12px",
        }}
      >
        <div className="card">
          <h3 style={{ fontSize: "14px", marginBottom: "10px" }}>
            Account Information
          </h3>
          <div style={{ marginBottom: "8px" }}>
            <strong>User ID:</strong> {user.id}
          </div>
          <div style={{ marginBottom: "8px" }}>
            <strong>Email:</strong> {user.email}
          </div>
          <div style={{ marginBottom: "8px" }}>
            <strong>Status:</strong>{" "}
            <span className="badge badge-completed">{user.accountStatus}</span>
          </div>
          <div style={{ marginBottom: "8px" }}>
            <strong>Authorization role:</strong> {user.authRole}
          </div>
          <div style={{ marginBottom: "12px" }}>
            <strong>Credit Balance:</strong> {availableCredits} Credits
          </div>
          <div style={{ borderTop: "1px solid #CCCCCC", paddingTop: "10px" }}>
            <div style={{ marginBottom: "6px" }}>
              <strong>Active Role:</strong> {user.activeRoleMode}
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
              <button
                className={`btn ${role === "REQUESTER" ? "btn-primary" : "btn-secondary"} btn-sm`}
                onClick={() => setRole("REQUESTER")}
                disabled={switchingRole}
              >
                Requester
              </button>
              <button
                className={`btn ${role === "COURIER" ? "btn-primary" : "btn-secondary"} btn-sm`}
                onClick={() => setRole("COURIER")}
                disabled={switchingRole}
              >
                Courier
              </button>
            </div>
          </div>
        </div>
        <div className="card">
          <h3 style={{ fontSize: "14px", marginBottom: "10px" }}>
            Edit Profile
          </h3>
          <form onSubmit={handleSave}>
            {field("Display Name", "display_name")}
            <div className="form-group">
              <label htmlFor="contact_preference">
                Preferred contact method
              </label>
              <select
                id="contact_preference"
                value={form.contact_preference}
                onChange={(event) =>
                  setForm({ ...form, contact_preference: event.target.value })
                }
              >
                <option value="">None</option>
                <option value="TELEGRAM">Telegram</option>
                <option value="EMAIL">Email</option>
                <option value="PHONE">Phone</option>
              </select>
            </div>
            {field("Telegram Handle", "telegram_handle")}
            {field("Phone Number", "phone_number", "tel")}
            {field("Profile Picture URL", "profile_picture_url", "url")}
            {actionError && (
              <div className="action-error" role="alert">
                {actionError}
              </div>
            )}
            <button
              type="submit"
              className="btn btn-primary btn-sm"
              disabled={saving}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
