import React, { useState } from "react";
import Navbar from "./components/Navbar";
import SuppliersSection from "./components/SuppliersSection";
import CreateOrderModal from "./components/CreateOrderModal";
import RequesterOrdersSection from "./components/RequesterOrdersSection";
import CourierOrdersSection from "./components/CourierOrdersSection";
import CourierActiveSection from "./components/CourierActiveSection";
import CreditsSection from "./components/CreditsSection";
import ProfileSection from "./components/ProfileSection";
import {
  initialSuppliers,
  initialOrders,
  initialTransactions,
} from "./data/mockData";

function goToScreen(screen) {
  window.location.href = `?screen=${screen}`;
}

function SimpleField({ label, type = "text", placeholder, required = false }) {
  return (
    <div className="form-group">
      <label>{label}{required ? " *" : ""}</label>
      <input type={type} placeholder={placeholder} required={required} />
    </div>
  );
}

function AuthScreen({ registration }) {
  return (
    <main className="main-content auth-screen">
      <div className="auth-panel">
        <h1>{registration ? "Create Account" : "Log In"}</h1>
        <p className="auth-help">{registration ? "Create an account with your NUS email." : "Sign in to Friend on Campus."}</p>
        <form onSubmit={(event) => { event.preventDefault(); goToScreen(registration ? "profile" : "suppliers"); }}>
          <SimpleField label="NUS email" type="email" placeholder="name@u.nus.edu" required />
          {registration && <SimpleField label="Display name" placeholder="Your name" required />}
          <SimpleField label="Password" type="password" placeholder="Password" required />
          {registration && <div className="field-error">Password must contain at least 8 characters.</div>}
          <button type="submit" className="btn btn-primary btn-block">{registration ? "Register" : "Log in"}</button>
        </form>
        <div className="auth-divider" />
        <button className="btn btn-secondary btn-block" onClick={() => goToScreen(registration ? "login" : "register")}>
          {registration ? "Back to login" : "Create an account"}
        </button>
        {!registration && <div className="action-error">Invalid email or password.</div>}
      </div>
    </main>
  );
}

function SupplierDetailScreen({ supplier, onChoose }) {
  return (
    <main className="main-content">
      <div className="section-header"><h2>Supplier Details</h2></div>
      <div className="card detail-card">
        <h3>{supplier.name}</h3>
        <p><strong>Campus location:</strong> {supplier.location}</p>
        <p><strong>Description:</strong> {supplier.description}</p>
        <p><strong>Pickup instructions:</strong> {supplier.pickupNotes}</p>
        <p><strong>Operating hours:</strong> {supplier.operatingHours}</p>
        <div className="detail-actions">
          <button className="btn btn-secondary" onClick={() => goToScreen("suppliers")}>Back</button>
          <button className="btn btn-primary" onClick={onChoose}>Choose supplier</button>
        </div>
      </div>
    </main>
  );
}

function CourierDetailScreen({ order, onAccept }) {
  return (
    <main className="main-content">
      <div className="section-header"><h2>Courier Order Details</h2></div>
      <div className="card detail-card">
        <h3>{order.id} - {order.supplierName}</h3>
        <p><strong>Pickup:</strong> {order.pickupLocation}</p>
        <p><strong>Item:</strong> {order.items}</p>
        <p><strong>Delivery:</strong> {order.deliveryLocation}</p>
        <p><strong>Instructions:</strong> {order.instructions}</p>
        <p><strong>Expiry:</strong> {order.deadline}</p>
        <p><strong>Requester:</strong> {order.requesterName}</p>
        <div className="action-error">Example status: this order may already be assigned.</div>
        <div className="detail-actions">
          <button className="btn btn-secondary" onClick={() => goToScreen("courier-orders")}>Back</button>
          <button className="btn btn-primary" onClick={onAccept}>Accept order</button>
        </div>
      </div>
    </main>
  );
}

function RequestErrorScreen() {
  return (
    <main className="main-content">
      <div className="section-header"><h2>Request Error / Pending State</h2></div>
      <div className="card">
        <div className="form-group"><label>Delivery location *</label><input placeholder="Required field" /></div>
        <div className="field-error">Delivery location is required.</div>
        <div className="action-error">Credit reservation is pending. The request has not been opened yet.</div>
        <button className="btn btn-secondary" onClick={() => goToScreen("create-request")}>Back to request</button>
      </div>
    </main>
  );
}

export default function App() {
  // Current logged in user (NUS student)
  const [user, setUser] = useState({
    id: "usr-1",
    name: "Student User",
    email: "student1@u.nus.edu",
    telegram: "@student1",
  });

  // Main UI States
  const screen = new URLSearchParams(window.location.search).get("screen");
  const initialTab = {
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
  }[screen] || "suppliers";
  const initialRole = [
    "courier",
    "openOrders",
    "open-orders",
    "courier-orders",
    "assignment",
  ].includes(screen)
    ? "COURIER"
    : "REQUESTER";
  const [role, setRole] = useState(initialRole); // 'REQUESTER' | 'COURIER'
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
  const [selectedSupplierForOrder, setSelectedSupplierForOrder] =
    useState(screen === "create-request" ? initialSuppliers[0] : null);

  const routeSupplier = suppliers.find((supplier) => supplier.id === "sup-1") || suppliers[0];
  const routeOrder = orders.find((order) => order.id === "REQ-102") || orders[0];

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

  if (screen === "login") return <AuthScreen registration={false} />;
  if (screen === "register") return <AuthScreen registration />;
  if (screen === "supplier-detail") {
    return <><Navbar role={role} setRole={setRole} activeTab={activeTab} setActiveTab={setActiveTab} availableCredits={availableCredits} user={user} /><SupplierDetailScreen supplier={routeSupplier} onChoose={() => handleQuickOpenModal(routeSupplier)} /><CreateOrderModal isOpen={isOrderModalOpen} onClose={() => setIsOrderModalOpen(false)} supplier={selectedSupplierForOrder} availableCredits={availableCredits} onSubmitOrder={handleCreateOrder} /></>;
  }
  if (screen === "courier-detail") {
    return <><Navbar role="COURIER" setRole={setRole} activeTab="courier-browse" setActiveTab={setActiveTab} availableCredits={availableCredits} user={user} /><CourierDetailScreen order={routeOrder} onAccept={() => handleAcceptOrder(routeOrder.id)} /></>;
  }
  if (screen === "request-error") return <><Navbar role="REQUESTER" setRole={setRole} activeTab="my-requests" setActiveTab={setActiveTab} availableCredits={availableCredits} user={user} /><RequestErrorScreen /></>;

  return (
    <div className="app-root">
      {/* Top Navigation */}
      <Navbar
        role={role}
        setRole={setRole}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        availableCredits={availableCredits}
        user={user}
      />

      {/* Main Sections */}
      <main className="main-content">
        {/* REQUESTER FLOWS */}
        {role === "REQUESTER" && activeTab === "suppliers" && (
          <SuppliersSection
            suppliers={suppliers}
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
            onUpdateUser={setUser}
            role={role}
            setRole={setRole}
            availableCredits={availableCredits}
          />
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
