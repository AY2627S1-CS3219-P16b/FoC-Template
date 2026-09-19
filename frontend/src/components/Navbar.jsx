import React from 'react';

export default function Navbar({
  role,
  setRole,
  roleError,
  switchingRole,
  activeTab,
  setActiveTab,
  availableCredits,
  onLogout,
}) {
  return (
    <header className="header">
      <div className="header-container">
        <div
          className="brand"
          onClick={() => setActiveTab(role === 'REQUESTER' ? 'suppliers' : 'courier-browse')}
        >
          Friend on Campus (FoC)
        </div>

        <div className="header-actions">
          <div className="role-switcher">
            <button
              className={`role-btn ${role === 'REQUESTER' ? 'active' : ''}`}
              onClick={() => setRole('REQUESTER')}
              disabled={switchingRole}
            >
              Requester Mode
            </button>
            <button
              className={`role-btn ${role === 'COURIER' ? 'active' : ''}`}
              onClick={() => setRole('COURIER')}
              disabled={switchingRole}
            >
              Courier Mode
            </button>
          </div>
          {roleError && <div className="action-error" role="alert">{roleError}</div>}

          <nav className="nav-tabs">
            {role === 'REQUESTER' ? (
              <>
                <button
                  className={`nav-tab ${activeTab === 'suppliers' ? 'active' : ''}`}
                  onClick={() => setActiveTab('suppliers')}
                >
                  Suppliers
                </button>
                <button
                  className={`nav-tab ${activeTab === 'my-requests' ? 'active' : ''}`}
                  onClick={() => setActiveTab('my-requests')}
                >
                  My Requests
                </button>
              </>
            ) : (
              <>
                <button
                  className={`nav-tab ${activeTab === 'courier-browse' ? 'active' : ''}`}
                  onClick={() => setActiveTab('courier-browse')}
                >
                  Open Orders
                </button>
                <button
                  className={`nav-tab ${activeTab === 'courier-active' ? 'active' : ''}`}
                  onClick={() => setActiveTab('courier-active')}
                >
                  Active Assignment
                </button>
              </>
            )}

            <button
              className={`nav-tab ${activeTab === 'credits' ? 'active' : ''}`}
              onClick={() => setActiveTab('credits')}
            >
              Credits
            </button>

            <button
              className={`nav-tab ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              Profile
            </button>
          </nav>

          <button
            className="credit-badge-btn"
            onClick={() => setActiveTab('credits')}
          >
            Credits: {availableCredits}
          </button>
          <button className="btn btn-primary logout-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}
