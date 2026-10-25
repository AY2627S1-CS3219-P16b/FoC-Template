import React from "react";
import OrderCard from "./OrderCard";
import Icon from "./Icon";

export default function RequesterOrdersSection({ orders, onCancelOrder, onConfirmDelivery, onNewRequestClick }) {
  return (
    <section>
      <div className="section-header compact-heading"><h2>My requests</h2><button type="button" className="btn btn-primary" onClick={onNewRequestClick}><Icon name="plus" />New Request</button></div>
      {orders.length ? <div className="orders-grid">{orders.map((order) => {
        const notice = ["RESERVING", "CANCELLING", "EXPIRING", "COMPLETING"].includes(order.status)
          ? <div className="notice-box order-notice">Credit processing is pending. Your request will update automatically.</div>
          : order.status === "REJECTED" ? <div className="action-error order-notice">Credits could not be reserved. Check your balance before creating another request.</div> : null;
        return <OrderCard key={order.id} order={order} notice={notice}>
          {order.status === "OPEN" && <button type="button" className="btn btn-secondary" onClick={() => onCancelOrder(order.id)}>Cancel Request</button>}
          {order.status === "DELIVERED" && <button type="button" className="btn btn-primary" onClick={() => onConfirmDelivery(order.id)}>Confirm Delivery<Icon name="arrow" /></button>}
        </OrderCard>;
      })}</div> : <div className="empty-state"><span className="empty-icon"><Icon name="list" /></span><h3>Your first errand starts here</h3><p>Choose a campus supplier and let someone help with the pickup.</p><button type="button" className="btn btn-primary" onClick={onNewRequestClick}>Browse Suppliers<Icon name="arrow" /></button></div>}
    </section>
  );
}
