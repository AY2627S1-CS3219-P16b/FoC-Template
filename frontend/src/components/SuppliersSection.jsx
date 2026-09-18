import React, { useState } from 'react';

export default function SuppliersSection({ suppliers, onQuickOpenModal }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  const filteredSuppliers = suppliers.filter(sup => {
    const matchesCategory = selectedCategory === 'ALL' || sup.category === selectedCategory;
    const matchesSearch =
      sup.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sup.location.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <section>
      <div className="section-header">
        <h2>Suppliers & Campus Facilities</h2>
      </div>

      <div className="filter-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Search suppliers or locations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <select
          className="filter-select"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
        >
          <option value="ALL">All Categories</option>
          <option value="F&B">F&B</option>
          <option value="Facilities">Facilities</option>
          <option value="Retail">Retail</option>
        </select>
      </div>

      {filteredSuppliers.length > 0 ? (
        <div className="grid-suppliers">
          {filteredSuppliers.map((sup) => (
            <div key={sup.id} className="card">
              <div className="supplier-name">{sup.name}</div>
              <div className="supplier-info"><strong>Location:</strong> {sup.location}</div>
              <div className="supplier-info"><strong>Category:</strong> {sup.category}</div>
              <div className="supplier-info"><strong>Hours:</strong> {sup.operatingHours}</div>
              <div className="supplier-info"><strong>Description:</strong> {sup.description}</div>
              <div className="supplier-info"><strong>Notes:</strong> {sup.pickupNotes}</div>

              <div style={{ marginTop: '10px' }}>
                <button
                  className="btn btn-primary btn-block"
                  onClick={() => onQuickOpenModal(sup)}
                >
                  Create Request
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>No suppliers found matching the criteria.</p>
        </div>
      )}
    </section>
  );
}
