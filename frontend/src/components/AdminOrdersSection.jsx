import React, { useEffect, useState } from "react";
import { listAdminOrders } from "../api/orders";

const STATUSES = [
  "RESERVING", "OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING",
  "COMPLETED", "CANCELLING", "CANCELLED", "EXPIRING", "EXPIRED", "REJECTED",
];

export default function AdminOrdersSection({ token, accounts }) {
  const [requesterId, setRequesterId] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    listAdminOrders(token, { page, requesterId, status })
      .then((data) => { if (active) setResult(data); })
      .catch((loadError) => { if (active) setError(loadError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, page, requesterId, status, refresh]);

  const person = (id) => {
    const account = accounts.find((entry) => entry.id === id);
    return account ? `${account.display_name} (${account.email}) · ${id}` : id;
  };

  return (
    <section style={{ marginTop: "12px" }}>
      <div className="section-header">
        <h2>All Order Requests</h2>
        <button type="button" className="btn btn-secondary btn-sm" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>Refresh</button>
      </div>
      <div className="card">
        <div className="form-group">
          <label htmlFor="admin-order-requester">Requester</label>
          <select id="admin-order-requester" value={requesterId} onChange={(event) => { setRequesterId(event.target.value); setPage(1); }}>
            <option value="">All requesters</option>
            {accounts.map((account) => <option key={account.id} value={account.id}>{account.display_name} · {account.email}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="admin-order-status">Order status</label>
          <select id="admin-order-status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {STATUSES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
          </select>
        </div>
      </div>
      {error && <div className="action-error" role="alert">{error}</div>}
      {loading && <p>Loading orders...</p>}
      {!loading && !error && result && (
        <>
          <p>{result.total} order requests</p>
          {result.items.length === 0 && <p>No matching order requests.</p>}
          {result.items.map((order) => (
            <article className="card" key={order.id}>
              <h3>Order {order.id} · {order.supplier_name}</h3>
              <p><strong>Status:</strong> {order.status.replaceAll("_", " ")}</p>
              <p><strong>Requester:</strong> {person(order.requester_user_id)}</p>
              <p><strong>Assigned courier:</strong> {order.courier_user_id ? person(order.courier_user_id) : "Unassigned"}</p>
              <p><strong>Items:</strong> {order.item_description}</p>
              <p><strong>Pickup:</strong> {order.pickup_location}</p>
              <p><strong>Delivery:</strong> {order.delivery_location}</p>
              <p><strong>Instructions:</strong> {order.delivery_instructions || "None"}</p>
              <p><strong>Reward:</strong> {order.credit_amount} credits</p>
              <p><strong>Acceptance deadline:</strong> {new Date(order.expires_at).toLocaleString()}</p>
              <p><strong>Created:</strong> {new Date(order.created_at).toLocaleString()} · <strong>Updated:</strong> {new Date(order.updated_at).toLocaleString()}</p>
            </article>
          ))}
          {result.total_pages > 1 && (
            <nav className="audit-pagination" aria-label="Admin order pages">
              <button type="button" className="btn btn-secondary btn-sm" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
              <span>Page {page} of {result.total_pages}</span>
              <button type="button" className="btn btn-secondary btn-sm" disabled={page >= result.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
            </nav>
          )}
        </>
      )}
    </section>
  );
}
