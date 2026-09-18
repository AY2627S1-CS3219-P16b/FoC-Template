import React, { useState } from 'react';

export default function CourierOrdersSection({
  orders,
  currentUserId,
  onAcceptOrder,
  hasActiveTask
}) {
  const [search, setSearch] = useState('');

  const openOrders = orders.filter(o => o.status === 'OPEN');
  const filteredOrders = openOrders.filter(o =>
    o.supplierName.toLowerCase().includes(search.toLowerCase()) ||
    o.deliveryLocation.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <section>
      <div className="section-header">
        <h2>Open Errand Requests</h2>
      </div>

      <div className="notice-box">
        Note: You cannot accept your own request. Only 1 courier can be assigned per order.
      </div>

      <div className="filter-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Filter by location or supplier..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {filteredOrders.length > 0 ? (
        <div>
          {filteredOrders.map((order) => {
            const isOwnOrder = order.requesterId === currentUserId;

            return (
              <div key={order.id} className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong>Order {order.id} - {order.supplierName}</strong>
                  <span className="badge badge-open">+{order.creditsReward} Credit</span>
                </div>

                <div style={{ marginBottom: '4px' }}><strong>Pickup:</strong> {order.pickupLocation}</div>
                <div style={{ marginBottom: '4px' }}><strong>Deliver to:</strong> {order.deliveryLocation}</div>
                <div style={{ marginBottom: '4px' }}><strong>Items:</strong> {order.items}</div>
                <div style={{ marginBottom: '4px' }}><strong>Requester:</strong> {order.requesterName}</div>
                <div style={{ marginBottom: '10px', fontSize: '12px', color: '#666666' }}>
                  Deadline: {order.deadline}
                </div>

                <div>
                  {isOwnOrder ? (
                    <button className="btn btn-secondary btn-sm" disabled>
                      Cannot Accept Own Order
                    </button>
                  ) : hasActiveTask ? (
                    <button className="btn btn-secondary btn-sm" disabled>
                      Active Task In Progress
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => onAcceptOrder(order.id)}
                    >
                      Accept Order
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <p>No open orders currently available.</p>
        </div>
      )}
    </section>
  );
}
