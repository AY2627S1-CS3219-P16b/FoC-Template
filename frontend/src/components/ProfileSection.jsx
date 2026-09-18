import React, { useState } from 'react';

export default function ProfileSection({
  user,
  onUpdateUser,
  role,
  setRole,
  availableCredits
}) {
  const [displayName, setDisplayName] = useState(user.name);
  const [telegram, setTelegram] = useState(user.telegram || '@student1');
  const [savedMsg, setSavedMsg] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    onUpdateUser({ ...user, name: displayName, telegram });
    setSavedMsg(true);
    setTimeout(() => setSavedMsg(false), 2000);
  };

  return (
    <section>
      <div className="section-header">
        <h2>User Profile</h2>
      </div>

      {savedMsg && (
        <div className="notice-box" style={{ borderColor: '#16A34A', color: '#16A34A' }}>
          Profile saved.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        <div className="card">
          <h3 style={{ fontSize: '14px', marginBottom: '10px' }}>Account Information</h3>

          <div style={{ marginBottom: '8px' }}>
            <strong>Email:</strong> {user.email}
          </div>

          <div style={{ marginBottom: '8px' }}>
            <strong>Status:</strong> <span className="badge badge-completed">ACTIVE</span>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <strong>Credit Balance:</strong> {availableCredits} Credits
          </div>

          <div style={{ borderTop: '1px solid #CCCCCC', paddingTop: '10px' }}>
            <div style={{ marginBottom: '6px' }}><strong>Active Role:</strong></div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                className={`btn ${role === 'REQUESTER' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                onClick={() => setRole('REQUESTER')}
              >
                Requester
              </button>
              <button
                className={`btn ${role === 'COURIER' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                onClick={() => setRole('COURIER')}
              >
                Courier
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '14px', marginBottom: '10px' }}>Edit Profile</h3>

          <form onSubmit={handleSave}>
            <div className="form-group">
              <label>Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Telegram Handle</label>
              <input
                type="text"
                value={telegram}
                onChange={(e) => setTelegram(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary btn-sm">
              Save
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
