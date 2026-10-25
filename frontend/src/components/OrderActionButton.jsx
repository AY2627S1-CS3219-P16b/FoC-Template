import React from "react";
import Icon from "./Icon";

const actions = {
  accept: ["Accept Order", "Accepting…"],
  cancel: ["Cancel Request", "Cancelling…"],
  confirm: ["Confirm Delivery", "Confirming…"],
  pickup: ["Mark Picked Up", "Updating…"],
  deliver: ["Mark Delivered", "Updating…"],
};

export default function OrderActionButton({ action, pendingAction, disabled = false, onClick }) {
  const [label, progressLabel] = actions[action];
  const busy = pendingAction === action;
  return (
    <button
      type="button"
      className={`btn ${action === "cancel" ? "btn-secondary" : "btn-primary"}`}
      disabled={disabled || !!pendingAction}
      aria-busy={busy}
      onClick={onClick}
    >
      {busy ? progressLabel : label}
      {!pendingAction && action !== "cancel" && <Icon name="arrow" />}
    </button>
  );
}
