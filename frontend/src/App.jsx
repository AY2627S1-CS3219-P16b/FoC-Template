import React, { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import SuppliersSection from "./components/SuppliersSection";
import CreateOrderModal from "./components/CreateOrderModal";
import RequesterOrdersSection from "./components/RequesterOrdersSection";
import CourierOrdersSection from "./components/CourierOrdersSection";
import CourierActiveSection from "./components/CourierActiveSection";
import CreditsSection from "./components/CreditsSection";
import ProfileSection from "./components/ProfileSection";
import AdminSection from "./components/AdminSection";
import SupplierAdminSection from "./components/SupplierAdminSection";
import {
  initialSuppliers,
  initialOrders,
  initialTransactions,
} from "./data/mockData";
import {
  getUserProfile,
  loginUser,
  registerUser,
  updateUserRoleMode,
  updateUserProfile,
} from "./api/users";

function goToScreen(screen) {
  window.location.href = `?screen=${screen}`;
}

function tokenPayload(token) {
  const encodedPayload = token.split(".")[1];
  const base64 = encodedPayload.replace(/-/g, "+").replace(/_/g, "/");
  const paddedBase64 = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  );
  return JSON.parse(atob(paddedBase64));
}

function getStoredAccessToken() {
  const token = localStorage.getItem("foc_access_token");
  if (!token) return null;

  try {
    const payload = tokenPayload(token);

    if (!payload.exp || payload.exp * 1000 <= Date.now()) {
      localStorage.removeItem("foc_access_token");
      localStorage.removeItem("foc_user");
      return null;
    }

    return token;
  } catch {
    localStorage.removeItem("foc_access_token");
    localStorage.removeItem("foc_user");
    return null;
  }
}

function PublicHeader() {
  return (
    <header className="landing-header">
      <span className="landing-brand">Friend on Campus</span>
      <span className="landing-brand-mark">FoC</span>
    </header>
  );
}

function LandingPage() {
  return (
    <div className="landing-page">
      <PublicHeader />
      <main className="landing-main">
        <section className="landing-card" aria-labelledby="landing-title">
          <h1 id="landing-title">Campus errands, shared.</h1>
          <p>
            Request an errand from around campus or help another student by
            completing one.
          </p>
          <div className="landing-actions">
            <button
              className="btn btn-primary landing-button"
              onClick={() => goToScreen("login")}
            >
              Log in
            </button>
            <button
              className="btn btn-secondary landing-button"
              onClick={() => goToScreen("register")}
            >
              Create account
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

function initialUser() {
  try {
    const authenticatedUser = JSON.parse(localStorage.getItem("foc_user"));
    if (authenticatedUser?.id) {
      return {
        id: authenticatedUser.id,
        name: authenticatedUser.display_name,
        email: authenticatedUser.email,
        telegram: "",
        contactPreference: null,
        phoneNumber: null,
        profilePictureUrl: null,
        authRole: authenticatedUser.auth_role,
        activeRoleMode: authenticatedUser.active_role_mode,
        accountStatus: authenticatedUser.account_status,
      };
    }
  } catch {
    localStorage.removeItem("foc_user");
  }

  const token = getStoredAccessToken();
  const userId = token ? tokenPayload(token).sub : "usr-1";
  return {
    id: userId,
    name: "Student User",
    email: "student1@u.nus.edu",
    telegram: "@student1",
    authRole: "USER",
    activeRoleMode: "REQUESTER",
    accountStatus: "ACTIVE",
  };
}

function profileToUser(profile) {
  return {
    id: profile.id,
    name: profile.display_name,
    email: profile.email,
    contactPreference: profile.contact_preference,
    telegram: profile.telegram_handle,
    phoneNumber: profile.phone_number,
    profilePictureUrl: profile.profile_picture_url,
    authRole: profile.auth_role,
    activeRoleMode: profile.active_role_mode,
    accountStatus: profile.account_status,
  };
}

function SimpleField({
  label,
  name,
  type = "text",
  placeholder,
  required = false,
  value,
  onChange,
  error,
}) {
  return (
    <div className="form-group">
      <label htmlFor={name}>
        {label}
        {required ? " *" : ""}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        placeholder={placeholder}
        required={required}
        value={value}
        onChange={onChange}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
      />
      {error && (
        <div id={`${name}-error`} className="field-error">
          {error}
        </div>
      )}
    </div>
  );
}

function SelectField({ label, name, value, onChange, options, error }) {
  return (
    <div className="form-group">
      <label htmlFor={name}>{label}</label>
      <select
        id={name}
        name={name}
        value={value}
        onChange={onChange}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
      >
        <option value="">Select a method (optional)</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <div id={`${name}-error`} className="field-error">
          {error}
        </div>
      )}
    </div>
  );
}

function AuthScreen({ registration }) {
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    contact_preference: "",
    telegram_handle: "",
    phone_number: "",
    profile_picture_url: "",
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [actionError, setActionError] = useState("");
  const [registered, setRegistered] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = ({ target: { name, value } }) => {
    setForm((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
    setActionError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setSubmitting(true);
    setFieldErrors({});
    setActionError("");
    try {
      if (registration) {
        await registerUser(form);
        setRegistered(true);
      } else {
        const session = await loginUser({
          email: form.email,
          password: form.password,
        });
        localStorage.setItem("foc_access_token", session.access_token);
        localStorage.setItem("foc_user", JSON.stringify(session.user));
        goToScreen(
          session.user.active_role_mode === "COURIER"
            ? "courier-orders"
            : "suppliers",
        );
      }
    } catch (error) {
      setFieldErrors(error.fieldErrors || {});
      if (!error.fieldErrors || Object.keys(error.fieldErrors).length === 0) {
        setActionError(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (registration && registered) {
    return (
      <div className="landing-page auth-page">
        <PublicHeader />
        <main className="landing-main auth-screen">
          <div className="auth-panel">
            <h1>Account created</h1>
            <div className="success-message" role="status">
              Your NUS student account is ready.
            </div>
            <button
              className="btn btn-primary btn-block"
              onClick={() => goToScreen("login")}
            >
              Continue to log in
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="landing-page auth-page">
      <PublicHeader />
      <main className="landing-main auth-screen">
        <div className="auth-panel">
          <h1>{registration ? "Create Account" : "Log In"}</h1>
          <p className="auth-help">
            {registration
              ? "Create an account with your NUS email."
              : "Sign in to Friend on Campus."}
          </p>
          <form onSubmit={handleSubmit} noValidate>
            <SimpleField
              label="NUS email"
              name="email"
              type="email"
              placeholder="e0123456@u.nus.edu"
              required
              value={form.email}
              onChange={handleChange}
              error={fieldErrors.email}
            />
            {registration && (
              <SimpleField
                label="Display name"
                name="display_name"
                placeholder="Your name"
                required
                value={form.display_name}
                onChange={handleChange}
                error={fieldErrors.display_name}
              />
            )}
            <SimpleField
              label="Password"
              name="password"
              type="password"
              placeholder="Password"
              required
              value={form.password}
              onChange={handleChange}
              error={fieldErrors.password}
            />
            {registration && (
              <>
                <p className="password-help">
                  Use at least 10 characters with uppercase, lowercase, a
                  number, and a symbol.
                </p>
                <details className="optional-fields">
                  <summary>Optional profile details</summary>
                  <SelectField
                    label="Preferred contact method"
                    name="contact_preference"
                    value={form.contact_preference}
                    onChange={handleChange}
                    error={fieldErrors.contact_preference}
                    options={[
                      { value: "TELEGRAM", label: "Telegram" },
                      { value: "EMAIL", label: "Email" },
                      { value: "PHONE", label: "Phone" },
                    ]}
                  />
                  <SimpleField
                    label="Telegram handle"
                    name="telegram_handle"
                    placeholder="@username"
                    value={form.telegram_handle}
                    onChange={handleChange}
                    error={fieldErrors.telegram_handle}
                  />
                  <SimpleField
                    label="Phone number"
                    name="phone_number"
                    type="tel"
                    placeholder="Phone number"
                    value={form.phone_number}
                    onChange={handleChange}
                    error={fieldErrors.phone_number}
                  />
                  <SimpleField
                    label="Profile picture URL"
                    name="profile_picture_url"
                    type="url"
                    placeholder="https://example.com/photo.jpg"
                    value={form.profile_picture_url}
                    onChange={handleChange}
                    error={fieldErrors.profile_picture_url}
                  />
                </details>
              </>
            )}
            {actionError && (
              <div className="action-error" role="alert">
                {actionError}
              </div>
            )}
            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={submitting}
            >
              {submitting
                ? registration
                  ? "Creating account…"
                  : "Signing in…"
                : registration
                  ? "Register"
                  : "Log in"}
            </button>
          </form>
          <div className="auth-divider" />
          <button
            className="btn btn-secondary btn-block"
            onClick={() => goToScreen(registration ? "login" : "register")}
          >
            {registration ? "Back to login" : "Create an account"}
          </button>
        </div>
      </main>
    </div>
  );
}

function SupplierDetailScreen({ supplier, onChoose }) {
  return (
    <main className="main-content">
      <div className="section-header">
        <h2>Supplier Details</h2>
      </div>
      <div className="card detail-card">
        <h3>{supplier.name}</h3>
        <p>
          <strong>Campus location:</strong> {supplier.location}
        </p>
        <p>
          <strong>Description:</strong> {supplier.description}
        </p>
        <p>
          <strong>Pickup instructions:</strong> {supplier.pickupNotes}
        </p>
        <p>
          <strong>Operating hours:</strong> {supplier.operatingHours}
        </p>
        <div className="detail-actions">
          <button
            className="btn btn-secondary"
            onClick={() => goToScreen("suppliers")}
          >
            Back
          </button>
          <button className="btn btn-primary" onClick={onChoose}>
            Choose supplier
          </button>
        </div>
      </div>
    </main>
  );
}

function CourierDetailScreen({ order, onAccept }) {
  return (
    <main className="main-content">
      <div className="section-header">
        <h2>Courier Order Details</h2>
      </div>
      <div className="card detail-card">
        <h3>
          {order.id} - {order.supplierName}
        </h3>
        <p>
          <strong>Pickup:</strong> {order.pickupLocation}
        </p>
        <p>
          <strong>Item:</strong> {order.items}
        </p>
        <p>
          <strong>Delivery:</strong> {order.deliveryLocation}
        </p>
        <p>
          <strong>Instructions:</strong> {order.instructions}
        </p>
        <p>
          <strong>Expiry:</strong> {order.deadline}
        </p>
        <p>
          <strong>Requester:</strong> {order.requesterName}
        </p>
        <div className="action-error">
          Example status: this order may already be assigned.
        </div>
        <div className="detail-actions">
          <button
            className="btn btn-secondary"
            onClick={() => goToScreen("courier-orders")}
          >
            Back
          </button>
          <button className="btn btn-primary" onClick={onAccept}>
            Accept order
          </button>
        </div>
      </div>
    </main>
  );
}

function RequestErrorScreen() {
  return (
    <main className="main-content">
      <div className="section-header">
        <h2>Request Error / Pending State</h2>
      </div>
      <div className="card">
        <div className="form-group">
          <label>Delivery location *</label>
          <input placeholder="Required field" />
        </div>
        <div className="field-error">Delivery location is required.</div>
        <div className="action-error">
          Credit reservation is pending. The request has not been opened yet.
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => goToScreen("create-request")}
        >
          Back to request
        </button>
      </div>
    </main>
  );
}

export default function App() {
  const accessToken = getStoredAccessToken();

  const handleLogout = () => {
    localStorage.removeItem("foc_access_token");
    localStorage.removeItem("foc_user");
    window.location.href = window.location.pathname;
  };

  // Current logged in user (NUS student)
  const [user, setUser] = useState(initialUser);
  const [profileError, setProfileError] = useState("");
  const [roleError, setRoleError] = useState("");
  const [switchingRole, setSwitchingRole] = useState(false);

  useEffect(() => {
    if (!accessToken) return;
    getUserProfile(accessToken, user.id)
      .then((profile) => {
        setUser(profileToUser(profile));
        setRole(profile.active_role_mode);
        setActiveTab((current) => {
          if (
            profile.active_role_mode === "COURIER" &&
            ["suppliers", "my-requests"].includes(current)
          )
            return "courier-browse";
          if (
            profile.active_role_mode === "REQUESTER" &&
            ["courier-browse", "courier-active"].includes(current)
          )
            return "suppliers";
          return current;
        });
        localStorage.setItem(
          "foc_user",
          JSON.stringify({
            id: profile.id,
            display_name: profile.display_name,
            email: profile.email,
            auth_role: profile.auth_role,
            active_role_mode: profile.active_role_mode,
            account_status: profile.account_status,
          }),
        );
      })
      .catch((error) => setProfileError(error.message));
  }, [accessToken, user.id]);

  const handleProfileUpdate = async (changes) => {
    const profile = await updateUserProfile(accessToken, user.id, changes);
    setUser(profileToUser(profile));
    setProfileError("");
  };

  const handleRoleChange = async (mode) => {
    if (switchingRole) return; // disable role switching while already in progress
    const nextTab = mode === "COURIER" ? "courier-browse" : "suppliers";
    if (mode === role) {
      setActiveTab(nextTab);
      return;
    }
    setSwitchingRole(true);
    setRoleError("");
    try {
      const profile = await updateUserRoleMode(accessToken, user.id, mode);
      setUser(profileToUser(profile));
      setRole(profile.active_role_mode);
      setActiveTab(nextTab);
      localStorage.setItem(
        "foc_user",
        JSON.stringify({
          id: profile.id,
          display_name: profile.display_name,
          email: profile.email,
          auth_role: profile.auth_role,
          active_role_mode: profile.active_role_mode,
          account_status: profile.account_status,
        }),
      );
    } catch (error) {
      setRoleError(error.message);
    } finally {
      setSwitchingRole(false);
    }
  };

  // Main UI States
  const screen = new URLSearchParams(window.location.search).get("screen");
  const initialTab =
    {
      suppliers: "suppliers",
      requester: "suppliers",
      requests: "my-requests",
      "requester-orders": "my-requests",
      courier: "courier-browse",
      openOrders: "courier-browse",
      "courier-orders": "courier-browse",
      "open-orders": "courier-browse",
      assignment: "courier-active",
      credits: "credits",
      profile: "profile",
      admin: "admin",
    }[screen] ||
    (user.activeRoleMode === "COURIER" ? "courier-browse" : "suppliers");
  const [role, setRole] = useState(user.activeRoleMode); // 'REQUESTER' | 'COURIER'
  const [activeTab, setActiveTab] = useState(initialTab); // 'suppliers', 'my-requests', 'courier-browse', 'courier-active', 'credits', 'profile'

  // Data States
  const [suppliers] = useState(initialSuppliers);
  const [orders, setOrders] = useState(initialOrders);
  const [transactions, setTransactions] = useState(initialTransactions);
  const [availableCredits, setAvailableCredits] = useState(20);
  const [reservedCredits, setReservedCredits] = useState(1);

  // Modal State
  const [isOrderModalOpen, setIsOrderModalOpen] = useState(
    screen === "create-request",
  );
  const [selectedSupplierForOrder, setSelectedSupplierForOrder] = useState(
    screen === "create-request" ? initialSuppliers[0] : null,
  );

  const routeSupplier =
    suppliers.find((supplier) => supplier.id === "sup-1") || suppliers[0];
  const routeOrder =
    orders.find((order) => order.id === "REQ-102") || orders[0];

  // Active courier task for the current user
  const activeCourierTask = orders.find(
    (o) =>
      o.courierId === user.id &&
      ["ACCEPTED", "PICKED_UP", "DELIVERED"].includes(o.status),
  );

  // Quick Open Modal from Supplier List
  const handleQuickOpenModal = (supplier) => {
    setSelectedSupplierForOrder(supplier);
    setIsOrderModalOpen(true);
  };

  // Requester: Submit New Errand Request
  const handleCreateOrder = (newOrderData) => {
    const newOrderId = `REQ-${Math.floor(1000 + Math.random() * 9000)}`;
    const newOrder = {
      id: newOrderId,
      ...newOrderData,
      requesterName: `${user.name} (You)`,
      requesterId: user.id,
      courierName: null,
      courierId: null,
      status: "OPEN",
      createdAt: "Just now",
    };

    // Deduct available credit and hold in reserve
    setAvailableCredits((prev) => prev - 1);
    setReservedCredits((prev) => prev + 1);

    // Record ledger transaction
    const newTx = {
      id: `TX-${Date.now()}`,
      time: "Just now",
      type: "CREDIT_RESERVED",
      title: `Errand Request Created (${newOrderData.supplierName})`,
      orderRef: `#${newOrderId}`,
      amount: -1,
      status: "HELD",
    };

    setOrders([newOrder, ...orders]);
    setTransactions([newTx, ...transactions]);
    setActiveTab("my-requests");
  };

  // Requester: Cancel Order
  const handleCancelOrder = (orderId) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: "CANCELLED" } : o)),
    );

    // Release reserved credit back to available balance
    setAvailableCredits((prev) => prev + 1);
    setReservedCredits((prev) => Math.max(0, prev - 1));

    // Record refund in transactions
    setTransactions((prev) => [
      {
        id: `TX-${Date.now()}`,
        time: "Just now",
        type: "CREDIT_RELEASED",
        title: "Order Cancelled by Requester",
        orderRef: `#${orderId}`,
        amount: 1,
        status: "RELEASED",
      },
      ...prev,
    ]);
  };

  // Requester: Confirm Delivery Receipt
  const handleConfirmDelivery = (orderId) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: "COMPLETED" } : o)),
    );

    // Deduct reserved credit permanently
    setReservedCredits((prev) => Math.max(0, prev - 1));

    setTransactions((prev) => [
      {
        id: `TX-${Date.now()}`,
        time: "Just now",
        type: "CREDIT_TRANSFERRED",
        title: "Delivery Confirmed & Credits Settled",
        orderRef: `#${orderId}`,
        amount: -1,
        status: "COMPLETED",
      },
      ...prev,
    ]);
  };

  // Courier: Accept Open Order
  const handleAcceptOrder = (orderId) => {
    setOrders((prev) =>
      prev.map((o) =>
        o.id === orderId
          ? {
              ...o,
              status: "ACCEPTED",
              courierName: user.name,
              courierId: user.id,
            }
          : o,
      ),
    );
    setActiveTab("courier-active");
  };

  // Courier: Mark Picked Up
  const handleMarkPickedUp = (orderId) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: "PICKED_UP" } : o)),
    );
  };

  // Courier: Mark Delivered
  const handleMarkDelivered = (orderId) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: "DELIVERED" } : o)),
    );
  };

  if (!accessToken && !["login", "register"].includes(screen)) {
    return <LandingPage />;
  }

  if (screen === "login") return <AuthScreen registration={false} />;
  if (screen === "register") return <AuthScreen registration />;
  if (screen === "supplier-detail") {
    return (
      <>
        <Navbar
          role={role}
          setRole={handleRoleChange}
          roleError={roleError}
          switchingRole={switchingRole}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          availableCredits={availableCredits}
          user={user}
          onLogout={handleLogout}
        />
        <SupplierDetailScreen
          supplier={routeSupplier}
          onChoose={() => handleQuickOpenModal(routeSupplier)}
        />
        <CreateOrderModal
          isOpen={isOrderModalOpen}
          onClose={() => setIsOrderModalOpen(false)}
          supplier={selectedSupplierForOrder}
          availableCredits={availableCredits}
          onSubmitOrder={handleCreateOrder}
        />
      </>
    );
  }
  if (screen === "courier-detail") {
    return (
      <>
        <Navbar
          role={role}
          setRole={handleRoleChange}
          roleError={roleError}
          switchingRole={switchingRole}
          activeTab="courier-browse"
          setActiveTab={setActiveTab}
          availableCredits={availableCredits}
          user={user}
          onLogout={handleLogout}
        />
        <CourierDetailScreen
          order={routeOrder}
          onAccept={() => handleAcceptOrder(routeOrder.id)}
        />
      </>
    );
  }
  if (screen === "request-error")
    return (
      <>
        <Navbar
          role={role}
          setRole={handleRoleChange}
          roleError={roleError}
          switchingRole={switchingRole}
          activeTab="my-requests"
          setActiveTab={setActiveTab}
          availableCredits={availableCredits}
          user={user}
          onLogout={handleLogout}
        />
        <RequestErrorScreen />
      </>
    );

  return (
    <div className="app-root">
      {/* Top Navigation */}
      <Navbar
        role={role}
        setRole={handleRoleChange}
        roleError={roleError}
        switchingRole={switchingRole}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        availableCredits={availableCredits}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Sections */}
      <main className="main-content">
        {/* REQUESTER FLOWS */}
        {role === "REQUESTER" && activeTab === "suppliers" && (
          <SuppliersSection
            token={accessToken}
            onQuickOpenModal={handleQuickOpenModal}
          />
        )}

        {role === "REQUESTER" && activeTab === "my-requests" && (
          <RequesterOrdersSection
            orders={orders.filter((o) => o.requesterId === user.id)}
            onCancelOrder={handleCancelOrder}
            onConfirmDelivery={handleConfirmDelivery}
            onNewRequestClick={() => setActiveTab("suppliers")}
          />
        )}

        {/* COURIER FLOWS */}
        {role === "COURIER" && activeTab === "courier-browse" && (
          <CourierOrdersSection
            orders={orders}
            currentUserId={user.id}
            onAcceptOrder={handleAcceptOrder}
            hasActiveTask={!!activeCourierTask}
          />
        )}

        {role === "COURIER" && activeTab === "courier-active" && (
          <CourierActiveSection
            activeTask={activeCourierTask}
            onMarkPickedUp={handleMarkPickedUp}
            onMarkDelivered={handleMarkDelivered}
            onFindNewTask={() => setActiveTab("courier-browse")}
          />
        )}

        {/* COMMON APP SECTIONS */}
        {activeTab === "credits" && (
          <CreditsSection
            availableCredits={availableCredits}
            reservedCredits={reservedCredits}
            transactions={transactions}
          />
        )}

        {activeTab === "profile" && (
          <ProfileSection
            user={user}
            onUpdateUser={handleProfileUpdate}
            loadError={profileError}
            role={role}
            setRole={handleRoleChange}
            switchingRole={switchingRole}
            availableCredits={availableCredits}
          />
        )}
        {activeTab === "admin" && (
          <>
            <AdminSection token={accessToken} currentUserId={user.id} />
            <SupplierAdminSection token={accessToken} />
          </>
        )}
      </main>

      {/* Order Creation Modal */}
      <CreateOrderModal
        isOpen={isOrderModalOpen}
        onClose={() => setIsOrderModalOpen(false)}
        supplier={selectedSupplierForOrder}
        availableCredits={availableCredits}
        onSubmitOrder={handleCreateOrder}
      />
    </div>
  );
}
