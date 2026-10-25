import React, { useState } from "react";
import OrderCard from "./OrderCard";
import Icon from "./Icon";

export default function CourierOrdersSection({ orders, currentUserId, onAcceptOrder, hasActiveTask }) {
  const [search, setSearch] = useState("");
  const openOrders = orders.filter((order) => order.status === "OPEN");
  const filteredOrders = openOrders.filter((order) => [order.supplierName, order.deliveryLocation, order.pickupLocation].join(" ").toLowerCase().includes(search.toLowerCase()));
  return (
    <section>
      <div className="section-header compact-heading">
        <h2>Open errands</h2>
        <span className="section-count">{openOrders.length} {openOrders.length === 1 ? "errand" : "errands"} available</span>
      </div>
      {hasActiveTask && <div className="notice-box">Finish your active assignment before accepting another errand.</div>}
      <div className="filter-bar order-filter-bar">
        <div className="search-field"><Icon name="search" /><input type="search" className="search-input" aria-label="Search open errands" placeholder="Search by supplier, pickup, or delivery location" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        <span className="filter-result-count">{filteredOrders.length} {filteredOrders.length === 1 ? "result" : "results"}</span>
      </div>
      {filteredOrders.length ? <div className="orders-grid">{filteredOrders.map((order) => <OrderCard key={order.id} order={order}>
        {order.requesterId === currentUserId ? <span className="order-action-hint">Your own request</span>
          : hasActiveTask ? <button type="button" className="btn btn-secondary" disabled>Active assignment in progress</button>
          : <button type="button" className="btn btn-primary" onClick={() => onAcceptOrder(order.id)}>Accept Order<Icon name="arrow" /></button>}
      </OrderCard>)}</div> : <div className="empty-state"><span className="empty-icon"><Icon name="bag" /></span><h3>{search ? "No errands match your search" : "You're all caught up"}</h3><p>{search ? "Try another supplier or location." : "New errands will appear here when students post them."}</p>{search && <button type="button" className="btn btn-secondary" onClick={() => setSearch("")}>Clear search</button>}</div>}
    </section>
  );
}
