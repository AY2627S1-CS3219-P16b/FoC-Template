import React from "react";
import Icon from "./Icon";

export default function Navbar({ role, setRole, roleError, switchingRole, activeTab, setActiveTab, availableCredits, user, onLogout }) {
  const navigate = (tab) => {
    const screen = new URLSearchParams(window.location.search).get("screen");
    if (["supplier-detail", "courier-detail", "request-error"].includes(screen)) {
      const routes = { "my-requests": "requests", "courier-browse": "courier-orders", "courier-active": "assignment" };
      window.location.href = "?screen=" + encodeURIComponent(routes[tab] || tab);
    } else {
      setActiveTab(tab);
    }
  };
  const primaryTabs = role === "REQUESTER"
    ? [{ id: "suppliers", label: "Suppliers", icon: "store" }, { id: "my-requests", label: "My Requests", icon: "list" }]
    : [{ id: "courier-browse", label: "Open Orders", icon: "bag" }, { id: "courier-active", label: "Active Assignment", icon: "pin" }];
  const tabs = [...primaryTabs, { id: "credits", label: "Credits", icon: "coins" }, { id: "profile", label: "Profile", icon: "user" }];
  return (
    <header className="header">
      <div className="header-container">
        <button type="button" className="brand" onClick={() => navigate(role === "REQUESTER" ? "suppliers" : "courier-browse")} aria-label="Friend on Campus home">
          <span className="brand-mark">FoC<span /></span><span className="brand-name">Friend on Campus</span>
        </button>
        <div className="role-switcher" aria-label="Working mode">
          {["REQUESTER", "COURIER"].map((mode) => <button key={mode} type="button" className={"role-btn " + (role === mode ? "active" : "")} aria-pressed={role === mode} disabled={switchingRole} onClick={() => setRole(mode)}>{mode === "REQUESTER" ? "Requester Mode" : "Courier Mode"}</button>)}
        </div>
        <div className="header-actions">
          <button type="button" className="credit-badge-btn" onClick={() => navigate("credits")} aria-label={(availableCredits ?? 0) + " available credits"}><Icon name="coins" /><strong>{availableCredits ?? 0}</strong><span>credits</span></button>
          <span className="header-user"><span className="user-avatar" aria-hidden="true">{(user?.name || "S").slice(0, 1).toUpperCase()}</span><span>{user?.name || "Student"}</span></span>
          <button type="button" className="btn btn-secondary logout-btn" onClick={onLogout} aria-label="Log out"><Icon name="logout" /><span className="logout-label">Log out</span></button>
        </div>
      </div>
      <div className="header-nav-container">
        <nav className="nav-tabs" aria-label="Main navigation">
          {tabs.map((tab) => <button key={tab.id} type="button" className={"nav-tab " + (activeTab === tab.id ? "active" : "")} aria-current={activeTab === tab.id ? "page" : undefined} onClick={() => navigate(tab.id)}><Icon name={tab.icon} />{tab.label}</button>)}
          {user?.authRole === "ADMIN" && <a className={"nav-tab nav-tab-admin " + (activeTab === "admin" ? "active" : "")} aria-current={activeTab === "admin" ? "page" : undefined} href="?screen=admin"><Icon name="shield" />Admin Access</a>}
        </nav>
      </div>
      {roleError && <div className="header-role-error action-error" role="alert">{roleError}</div>}
    </header>
  );
}
