import React, { useEffect, useState } from "react";
import { listAdminOrders, orderForDisplay } from "../api/orders";
import { OrderFacts, OrderStatus } from "./OrderCard";
import Icon from "./Icon";
import { creditLabel, formatOrderDate, shortOrderId, statusLabel } from "../utils/orderPresentation";

const STATUSES = [
  "RESERVING", "OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING",
  "COMPLETED", "CANCELLING", "CANCELLED", "EXPIRING", "EXPIRED", "REJECTED",
];

export default function AdminOrdersSection({ token, accounts }) {
  const [requesterId, setRequesterId] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [expandedId, setExpandedId] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setExpandedId(null);
    listAdminOrders(token, { page, requesterId, status })
      .then((data) => { if (active) setResult(data); })
      .catch((loadError) => { if (active) setError(loadError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, page, requesterId, status, refresh]);

  const accountFor = (id) => accounts.find((account) => account.id === id);
  const person = (id) => {
    if (!id) return "Unassigned";
    const account = accountFor(id);
    return account ? account.display_name : "Student " + shortOrderId(id);
  };
  const fullPerson = (id) => {
    if (!id) return "Unassigned";
    const account = accountFor(id);
    return account ? account.display_name + " (" + account.email + ") · " + id : id;
  };

  return (
    <section className="admin-orders-section">
      <div className="section-header">
        <div><p className="page-eyebrow">Order management</p><h2>All order requests</h2><p className="page-description">An overview of campus errands and their progress.</p></div>
        <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><Icon name="refresh" />{loading ? "Refreshing…" : "Refresh"}</button>
      </div>
      <div className="admin-order-filters card">
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
            {STATUSES.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}
          </select>
        </div>
        {(requesterId || status) && <button type="button" className="btn btn-secondary" onClick={() => { setRequesterId(""); setStatus(""); setPage(1); }}>Clear filters</button>}
      </div>
      {error && <div className="action-error" role="alert">{error}</div>}
      {loading && <p className="loading-state" role="status">Loading orders…</p>}
      {!loading && !error && result && (
        <>
          <p className="results-summary">{result.total} {result.total === 1 ? "order request" : "order requests"}{status ? " · " + statusLabel(status) : ""}</p>
          {result.items.length === 0 ? <div className="empty-state"><span className="empty-icon"><Icon name="list" /></span><h3>No matching orders</h3><p>Try a different requester or order status.</p></div>
            : <div className="table-container admin-orders-table-wrap"><table className="admin-orders-table">
              <caption className="sr-only">Order requests, with expandable details</caption>
              <thead><tr><th scope="col">Order</th><th scope="col">Requester</th><th scope="col">Status</th><th scope="col">Reward</th><th scope="col">Created</th><th scope="col"><span className="sr-only">Details</span></th></tr></thead>
              <tbody>{result.items.map((order) => {
                const expanded = expandedId === order.id;
                const detailId = "admin-order-details-" + order.id;
                return <React.Fragment key={order.id}>
                  <tr className={expanded ? "is-expanded" : ""}>
                    <td data-label="Order" className="admin-order-main"><span className="order-reference">#{shortOrderId(order.id)}</span><strong>{order.supplier_name}</strong><span className="table-order-items">{order.item_description}</span></td>
                    <td data-label="Requester"><span className="table-person">{person(order.requester_user_id)}</span></td>
                    <td data-label="Status"><OrderStatus status={order.status} /></td>
                    <td data-label="Reward" className="table-reward">{creditLabel(order.credit_amount)}</td>
                    <td data-label="Created"><time dateTime={order.created_at}>{formatOrderDate(order.created_at)}</time></td>
                    <td className="table-order-action"><button type="button" className="btn btn-secondary btn-sm" aria-expanded={expanded} aria-controls={detailId} aria-label={(expanded ? "Hide" : "View") + " details for order " + shortOrderId(order.id)} onClick={() => setExpandedId(expanded ? null : order.id)}>{expanded ? "Hide details" : "View details"}</button></td>
                  </tr>
                  <tr className="admin-order-detail-row" hidden={!expanded}>
                    <td colSpan={6}><div id={detailId} className="admin-order-detail">
                      <div className="admin-detail-route"><div><span className="field-caption">Pickup</span><p>{order.pickup_location}</p></div><Icon name="arrow" /><div><span className="field-caption">Deliver to</span><p>{order.delivery_location}</p></div></div>
                      <div className="admin-detail-items"><span className="field-caption">Items requested</span><p>{order.item_description}</p></div>
                      <OrderFacts order={orderForDisplay(order, "")} requester={fullPerson(order.requester_user_id)} courier={fullPerson(order.courier_user_id)} />
                    </div></td>
                  </tr>
                </React.Fragment>;
              })}</tbody>
            </table></div>}
          {result.total_pages > 1 && <nav className="audit-pagination" aria-label="Admin order pages">
            <button type="button" className="btn btn-secondary btn-sm" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
            <span>Page {page} of {result.total_pages}</span>
            <button type="button" className="btn btn-secondary btn-sm" disabled={page >= result.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
          </nav>}
        </>
      )}
    </section>
  );
}
