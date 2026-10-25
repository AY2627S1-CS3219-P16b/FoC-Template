import React from "react";
import Icon from "./Icon";
import { acceptanceDeadline, creditLabel, formatOrderDate, shortOrderId, statusLabel, statusTone } from "../utils/orderPresentation";

export function OrderStatus({ status }) {
  return <span className={`badge status-badge status-${statusTone(status)}`}><span className="status-dot" />{statusLabel(status)}</span>;
}

export function OrderFacts({ order, requester, courier }) {
  const facts = [
    ["Order ID", <code>{order.id}</code>],
    ["Requester", requester || order.requesterName || "Not available"],
    ["Assigned courier", courier || order.courierName || "Unassigned"],
    ["Delivery instructions", order.instructions && order.instructions !== "None" ? order.instructions : "No special instructions"],
    ["Acceptance deadline", order.expiresAt ? formatOrderDate(order.expiresAt, { detailed: true }) : order.deadline],
    ["Created", order.createdAtIso ? formatOrderDate(order.createdAtIso, { detailed: true }) : order.createdAt],
    ...(order.updatedAtIso ? [["Last updated", formatOrderDate(order.updatedAtIso, { detailed: true })]] : []),
  ];
  return <dl className="order-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Not available"}</dd></div>)}</dl>;
}

export default function OrderCard({ order, children, notice }) {
  const deadline = order.expiresAt ? acceptanceDeadline(order.expiresAt) : order.deadline;
  const urgent = order.status === "OPEN" && order.expiresAt
    && new Date(order.expiresAt).getTime() - Date.now() <= 5 * 60000;
  return (
    <article className="card order-card">
      <div className="order-card-header">
        <div className="order-card-heading"><OrderStatus status={order.status} /><h3>{order.supplierName}</h3></div>
        <span className="reward-chip"><Icon name="coins" />{creditLabel(order.creditsReward)}</span>
      </div>
      <p className="order-items">{order.items}</p>
      <div className="order-route">
        <div className="route-stop"><span className="route-icon route-pickup"><Icon name="store" /></span><div><span className="field-caption">Pickup</span><p>{order.pickupLocation}</p></div></div>
        <Icon name="arrow" className="route-arrow" />
        <div className="route-stop"><span className="route-icon route-delivery"><Icon name="pin" /></span><div><span className="field-caption">Deliver to</span><p>{order.deliveryLocation}</p></div></div>
      </div>
      <div className="order-meta">
        <span className="order-reference">#{shortOrderId(order.id)}</span>
        {order.status === "OPEN" ? <span className={urgent ? "deadline-urgent" : ""}><Icon name="clock" />{deadline}</span>
          : <span>{order.createdAtIso ? formatOrderDate(order.createdAtIso) : order.createdAt}</span>}
      </div>
      {notice}
      <div className="order-card-footer">
        <details className="order-details"><summary>View details</summary><OrderFacts order={order} /></details>
        {children && <div className="order-actions">{children}</div>}
      </div>
    </article>
  );
}
