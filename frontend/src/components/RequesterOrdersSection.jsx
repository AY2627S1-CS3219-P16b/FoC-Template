import React, { useEffect } from "react";
import OrderCard from "./OrderCard";
import Icon from "./Icon";
import OrderActionButton from "./OrderActionButton";
import useRequesterOrders from "../hooks/useRequesterOrders";

export default function RequesterOrdersSection({ token, userId, refreshTick, ...props }) {
  const state = useRequesterOrders({ token, userId, refreshTick });
  useEffect(() => { window.scrollTo(0, 0); }, [state.view, state.page]);
  return <RequesterOrdersView {...props} {...state} orders={state.result?.items || []}
    total={state.result?.total || 0} totalPages={state.result?.total_pages || 0} hasResult={!!state.result} />;
}

export function RequesterOrdersView({ orders = [], onCancelOrder, onConfirmDelivery, onNewRequestClick, pendingOrderActions = {},
  view = "active", page = 1, total = orders.length, totalPages = 1, loading = false, error = "", hasResult = true,
  onViewChange, onPageChange, onRefresh }) {
  return (
    <section>
      <div className="section-header compact-heading"><h2>My requests</h2><button type="button" className="btn btn-primary" onClick={onNewRequestClick}><Icon name="plus" />New Request</button></div>
      <div className="requests-toolbar">
        <div className="requests-view-switch" role="group" aria-label="Request status">
          {[["active", "Active"], ["past", "Past"]].map(([value, label]) => <button key={value} type="button" aria-pressed={view === value} onClick={() => onViewChange(value)}>{label}</button>)}
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRefresh} disabled={loading}><Icon name="refresh" />{loading ? "Refreshing…" : "Refresh"}</button>
      </div>
      {error && <div className="action-error" role="alert">{error}</div>}
      <div aria-busy={loading}>
      {!hasResult && loading && <p className="loading-state" role="status">Loading requests…</p>}
      {hasResult && <>
      <p className="results-summary" role="status">{total} {view} {total === 1 ? "request" : "requests"}</p>
      {orders.length ? <div className="orders-grid">{orders.map((order) => {
        const notice = ["RESERVING", "CANCELLING", "EXPIRING", "COMPLETING"].includes(order.status)
          ? <div className="notice-box order-notice">Credit processing is pending. Your request will update automatically.</div>
          : order.status === "REJECTED" ? <div className="action-error order-notice">Credits could not be reserved. Check your balance before creating another request.</div> : null;
        return <OrderCard key={order.id} order={order} notice={notice}>
          {order.status === "OPEN" && <OrderActionButton action="cancel" pendingAction={pendingOrderActions[order.id]} onClick={() => onCancelOrder(order.id)} />}
          {order.status === "DELIVERED" && <OrderActionButton action="confirm" pendingAction={pendingOrderActions[order.id]} onClick={() => onConfirmDelivery(order.id)} />}
        </OrderCard>;
      })}</div> : <div className="empty-state"><span className="empty-icon"><Icon name="list" /></span>
        <h3>{view === "past" ? "No past requests" : "No active requests"}</h3>
        <p>{view === "past" ? "Completed, cancelled, expired, and rejected requests appear here." : "Finished requests are under Past. Browse suppliers to create a new request."}</p>
        {view !== "past" && <button type="button" className="btn btn-primary" onClick={onNewRequestClick}>Browse Suppliers<Icon name="arrow" /></button>}
      </div>}
      {totalPages > 1 && <nav className="requests-pagination" aria-label="My request pages">
        <button type="button" className="btn btn-secondary" disabled={loading || page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button type="button" className="btn btn-secondary" disabled={loading || page >= totalPages} onClick={() => onPageChange(page + 1)}>Next</button>
      </nav>}
      </>}
      </div>
    </section>
  );
}
