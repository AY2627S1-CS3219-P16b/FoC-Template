import React from "react";
import OrderCard from "./OrderCard";
import Icon from "./Icon";

export default function CourierActiveSection({ activeTask, onMarkPickedUp, onMarkDelivered, onFindNewTask }) {
  const steps = ["Accepted", "Picked up", "Delivered", "Completed"];
  const currentStep = { ACCEPTED: 0, PICKED_UP: 1, DELIVERED: 2, COMPLETING: 2, COMPLETED: 3 }[activeTask?.status] ?? 0;
  return (
    <section>
      <div className="section-header compact-heading"><h2>Active assignment</h2></div>
      {!activeTask ? <div className="empty-state"><span className="empty-icon"><Icon name="pin" /></span><h3>Ready for your next errand?</h3><p>You don't have an active assignment right now.</p><button type="button" className="btn btn-primary" onClick={onFindNewTask}>Browse Open Orders<Icon name="arrow" /></button></div>
        : <div className="active-order-layout">
          <ol className="delivery-steps" aria-label="Delivery progress">{steps.map((step, index) => <li key={step} className={index <= currentStep ? "is-reached" : ""} aria-current={index === currentStep ? "step" : undefined}><span>{index < currentStep ? "✓" : index + 1}</span>{step}</li>)}</ol>
          <OrderCard order={activeTask} notice={
            activeTask.status === "DELIVERED" ? <div className="notice-box order-notice">Delivered. Waiting for the requester to confirm receipt.</div>
              : activeTask.status === "COMPLETING" ? <div className="notice-box order-notice">Receipt confirmed. Your credit reward is being processed.</div> : null
          }>
            {activeTask.status === "ACCEPTED" && <button type="button" className="btn btn-primary" onClick={() => onMarkPickedUp(activeTask.id)}>Mark Picked Up<Icon name="arrow" /></button>}
            {activeTask.status === "PICKED_UP" && <button type="button" className="btn btn-primary" onClick={() => onMarkDelivered(activeTask.id)}>Mark Delivered<Icon name="arrow" /></button>}
          </OrderCard>
        </div>}
    </section>
  );
}
