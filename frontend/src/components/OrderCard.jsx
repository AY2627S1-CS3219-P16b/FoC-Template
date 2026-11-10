import React from "react";
import Icon from "./Icon";
import { acceptanceDeadline, creditLabel, formatOrderDate, shortOrderId, statusLabel, statusTone } from "../utils/orderPresentation";
import { openOrderHelp } from "../utils/orderHelp";

export function OrderStatus({ status }) {
  return <span className={`badge status-badge status-${statusTone(status)}`}><span className="status-dot" />{statusLabel(status)}</span>;
}

const deliveryNote = (order) =>
  (order.instructions && order.instructions !== "None" ? order.instructions : "");

// showInstructions is off on order cards, which already show them under "Deliver to".
export function OrderFacts({ order, requester, courier, showInstructions = true }) {
  const facts = [
    ["Order ID", <code>{order.id}</code>],
    ["Requester", requester || order.requesterName || "Not available"],
    ["Assigned courier", courier || order.courierName || "Unassigned"],
    ...(showInstructions ? [["Delivery instructions", deliveryNote(order) || "No special instructions"]] : []),
    ["Acceptance deadline", order.expiresAt ? formatOrderDate(order.expiresAt, { detailed: true }) : order.deadline],
    ["Created", order.createdAtIso ? formatOrderDate(order.createdAtIso, { detailed: true }) : order.createdAt],
    ...(order.updatedAtIso ? [["Last updated", formatOrderDate(order.updatedAtIso, { detailed: true })]] : []),
  ];
  return <dl className="order-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Not available"}</dd></div>)}</dl>;
}

const CONTACT_LABELS = { TELEGRAM: "Telegram", PHONE: "Phone", EMAIL: "Email" };

/** A link that opens the chosen app, or null when the value cannot be linked safely. */
export function contactHref(preference, value) {
  if (!value) return null;
  if (preference === "TELEGRAM") {
    const handle = value.trim().replace(/^@/, "");
    return /^[A-Za-z0-9_]{3,32}$/.test(handle) ? `https://t.me/${handle}` : null;
  }
  if (preference === "PHONE") {
    const number = value.replace(/[^\d+]/g, "");
    return /^\+?\d{6,15}$/.test(number) ? `tel:${number}` : null;
  }
  if (preference === "EMAIL") return /^[^\s@]+@[^\s@]+$/.test(value) ? `mailto:${value}` : null;
  return null;
}

/** The other party's name and preferred contact, labelled from the viewer's side. */
function OrderContact({ contact, viewerRole }) {
  const who = viewerRole === "requester" ? "Your courier"
    : viewerRole === "courier" ? "Your requester" : "Contact";
  const method = CONTACT_LABELS[contact.contact_preference];
  const href = method && contactHref(contact.contact_preference, contact.contact);
  return (
    <div className="order-contact">
      <span className="route-icon"><Icon name="user" /></span>
      <div>
        <span className="field-caption">{who}</span>
        <p>
          <strong>{contact.display_name}</strong>
          {method && contact.contact ? <>
            <span className="contact-method">{method}</span>
            {href ? <a href={href} target="_blank" rel="noreferrer">{contact.contact}</a> : contact.contact}
          </> : <span className="contact-missing">No contact method shared</span>}
        </p>
      </div>
    </div>
  );
}

// helpRole ("requester" or "courier") adds a "Get help" link for the viewer's own orders.
export default function OrderCard({ order, children, notice, helpRole }) {
  const deadline = order.expiresAt ? acceptanceDeadline(order.expiresAt) : order.deadline;
  const urgent = order.status === "OPEN" && order.expiresAt
    && new Date(order.expiresAt).getTime() - Date.now() <= 5 * 60000;
  return (
    <article className="card order-card">
      <div className="order-card-header">
        <div className="order-card-heading"><OrderStatus status={order.status} /><h3>{order.supplierName}</h3></div>
        <span className="reward-chip"><Icon name="coins" />{creditLabel(order.creditsReward)}</span>
      </div>
      <div className="order-items-block"><span className="field-caption">Items</span><p className="order-items">{order.items}</p></div>
      <div className="order-route">
        <div className="route-stop"><span className="route-icon route-pickup"><Icon name="store" /></span><div><span className="field-caption">Pickup</span><p>{order.pickupLocation}</p></div></div>
        <Icon name="arrow" className="route-arrow" />
        <div className="route-stop"><span className="route-icon route-delivery"><Icon name="pin" /></span><div><span className="field-caption">Deliver to</span><p>{order.deliveryLocation}</p>{deliveryNote(order) && <p className="route-note">Note: {deliveryNote(order)}</p>}</div></div>
      </div>
      <div className="order-meta">
        <span className="order-reference">#{shortOrderId(order.id)}</span>
        {order.status === "OPEN" ? <span className={urgent ? "deadline-urgent" : ""}><Icon name="clock" />{deadline}</span>
          : <span>{order.createdAtIso ? formatOrderDate(order.createdAtIso) : order.createdAt}</span>}
      </div>
      {order.receiptConfirmationDeadline && <div className="notice-box order-notice">Receipt is confirmed automatically by {formatOrderDate(order.receiptConfirmationDeadline, { detailed: true })}. Confirm once you have your items.</div>}
      {order.contact && <OrderContact contact={order.contact} viewerRole={helpRole} />}
      {order.contactError && <p role="status">Contact details are unavailable. Retrying automatically.</p>}
      {order.creditError && <div className="action-error" role="alert">Credit processing needs admin attention.</div>}
      {notice}
      <div className="order-card-footer">
        <details className="order-details"><summary>View details</summary><OrderFacts order={order} showInstructions={false}
          requester={helpRole === "courier" ? order.contact?.display_name : undefined}
          courier={helpRole === "requester" ? order.contact?.display_name : undefined} /></details>
        {helpRole && <button type="button" className="order-help-link" onClick={() => openOrderHelp(order, helpRole)}>
          <Icon name="help" />Get help</button>}
        {children && <div className="order-actions">{children}</div>}
      </div>
    </article>
  );
}
