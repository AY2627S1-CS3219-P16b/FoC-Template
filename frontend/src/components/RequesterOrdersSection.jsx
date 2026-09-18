import React from 'react';

export default function RequesterOrdersSection({
  orders,
  onCancelOrder,
  onConfirmDelivery,
  onNewRequestClick
}) {
  return (
    <section>
      <div className="section-header">
        <h2>My Errand Requests</h2>
        <button className="btn btn-primary btn-sm" onClick={onNewRequestClick}>
          + New Request
        </button>
      </div>

      {orders.length > 0 ? (
        <div>
          {orders.map((order) => (
            <div key={order.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <strong>Order {order.id} - {order.supplierName}</strong>
                <span className={`badge badge-${order.status.toLowerCase().replace('_', '-')}`}>
                  {order.status}
                </span>
              </div>

              <div style={{ marginBottom: '6px' }}><strong>Pickup:</strong> {order.pickupLocation}</div>
              <div style={{ marginBottom: '6px' }}><strong>Delivery to:</strong> {order.deliveryLocation}</div>
              <div style={{ marginBottom: '6px' }}><strong>Items:</strong> {order.items}</div>
              <div style={{ marginBottom: '6px' }}><strong>Instructions:</strong> {order.instructions}</div>
              <div style={{ marginBottom: '6px' }}>
                <strong>Courier:</strong> {order.courierName || 'Unassigned'}
              </div>
              <div style={{ marginBottom: '10px', fontSize: '12px', color: '#666666' }}>
                Credits Reserved: {order.creditsReward} Credit | Created: {order.createdAt}
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                {order.status === 'OPEN' && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onCancelOrder(order.id)}
                  >
                    Cancel Request
                  </button>
                )}

                {order.status === 'DELIVERED' && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => onConfirmDelivery(order.id)}
                  >
                    Confirm Delivery
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No errand requests created yet.</p>
        </div>
      )}
    </section>
  );
}
