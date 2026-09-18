import React, { useState } from 'react';

export default function CreateOrderModal({
  isOpen,
  onClose,
  supplier,
  availableCredits,
  onSubmitOrder
}) {
  const [items, setItems] = useState('');
  const [deliveryLocation, setDeliveryLocation] = useState('');
  const [instructions, setInstructions] = useState('');
  const [deadline, setDeadline] = useState('Within 45 mins');
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen || !supplier) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!items.trim() || !deliveryLocation.trim()) {
      setErrorMsg('Please fill in required fields.');
      return;
    }

    if (availableCredits < 1) {
      setErrorMsg('Insufficient credit balance (Requires 1 credit).');
      return;
    }

    setErrorMsg('');
    onSubmitOrder({
      supplierId: supplier.id,
      supplierName: supplier.name,
      pickupLocation: supplier.location,
      items: items.trim(),
      deliveryLocation: deliveryLocation.trim(),
      instructions: instructions.trim() || 'None',
      deadline,
      creditsReward: 1
    });

    setItems('');
    setDeliveryLocation('');
    setInstructions('');
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create Errand Request</h3>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>X</button>
        </div>

        {errorMsg && (
          <div className="notice-box" style={{ borderColor: '#DC2626', color: '#DC2626' }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="card" style={{ background: '#F8F8F8', marginBottom: '10px' }}>
            <div><strong>Supplier:</strong> {supplier.name}</div>
            <div><strong>Pickup Location:</strong> {supplier.location}</div>
          </div>

          <div className="form-group">
            <label>Item Description *</label>
            <textarea
              rows={2}
              placeholder="e.g. Item 1, Item 2"
              value={items}
              onChange={(e) => setItems(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Delivery Location *</label>
            <input
              type="text"
              placeholder="e.g. Location 1"
              value={deliveryLocation}
              onChange={(e) => setDeliveryLocation(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Delivery Instructions</label>
            <input
              type="text"
              placeholder="e.g. Instructions 1"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label>Deadline</label>
            <select value={deadline} onChange={(e) => setDeadline(e.target.value)}>
              <option value="Within 30 mins">Within 30 mins</option>
              <option value="Within 45 mins">Within 45 mins</option>
              <option value="Within 1 hour">Within 1 hour</option>
            </select>
          </div>

          <div className="notice-box">
            Credit Reservation: 1 Credit will be held from available balance ({availableCredits} available).
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
              Submit Request
            </button>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
