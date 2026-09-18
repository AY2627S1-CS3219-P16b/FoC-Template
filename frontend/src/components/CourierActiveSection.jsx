import React from 'react';

export default function CourierActiveSection({
  activeTask,
  onMarkPickedUp,
  onMarkDelivered,
  onFindNewTask
}) {
  if (!activeTask) {
    return (
      <section>
        <div className="section-header">
          <h2>Active Assignment</h2>
        </div>

        <div className="empty-state">
          <p>No active errand assignment.</p>
          <button
            className="btn btn-primary btn-sm"
            style={{ marginTop: '10px' }}
            onClick={onFindNewTask}
          >
            Browse Open Orders
          </button>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="section-header">
        <h2>Active Assignment</h2>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <strong>Order {activeTask.id} - {activeTask.supplierName}</strong>
          <span className="badge badge-accepted">Status: {activeTask.status}</span>
        </div>

        <div style={{ marginBottom: '4px' }}><strong>Pickup:</strong> {activeTask.pickupLocation}</div>
        <div style={{ marginBottom: '4px' }}><strong>Deliver to:</strong> {activeTask.deliveryLocation}</div>
        <div style={{ marginBottom: '4px' }}><strong>Items:</strong> {activeTask.items}</div>
        <div style={{ marginBottom: '4px' }}><strong>Requester:</strong> {activeTask.requesterName}</div>
        <div style={{ marginBottom: '4px' }}><strong>Instructions:</strong> {activeTask.instructions}</div>
        <div style={{ marginBottom: '12px', fontSize: '12px', color: '#666666' }}>
          Reward: +{activeTask.creditsReward} Credit upon completion
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {activeTask.status === 'ACCEPTED' && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onMarkPickedUp(activeTask.id)}
            >
              Mark Picked Up
            </button>
          )}

          {activeTask.status === 'PICKED_UP' && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onMarkDelivered(activeTask.id)}
            >
              Mark Delivered
            </button>
          )}

          {activeTask.status === 'DELIVERED' && (
            <div className="notice-box" style={{ margin: 0 }}>
              Order marked as delivered. Waiting for requester confirmation.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
