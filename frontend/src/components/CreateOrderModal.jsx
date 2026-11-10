import React, { useEffect, useState } from 'react';
import { formatPlace } from '../api/suppliers';
import {
  DEFAULT_DEADLINE,
  closingNotice,
  deadlineChoices,
  effectiveDeadline,
} from '../utils/deadlines';

export default function CreateOrderModal({
  isOpen,
  onClose,
  supplier,
  availableCredits,
  balanceUnknown = false,
  onSubmitOrder
}) {
  const [items, setItems] = useState('');
  const [deliveryLocation, setDeliveryLocation] = useState('');
  const [instructions, setInstructions] = useState('');
  const [deadline, setDeadline] = useState(DEFAULT_DEADLINE);
  const [errorMsg, setErrorMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Each opening, and each different supplier, starts with an empty form.
  useEffect(() => {
    if (!isOpen) return;
    setItems('');
    setDeliveryLocation('');
    setInstructions('');
    setDeadline(DEFAULT_DEADLINE);
    setErrorMsg('');
  }, [isOpen, supplier?.id]);

  if (!isOpen || !supplier) return null;

  const pickupLocation = `${formatPlace(supplier.place)}${supplier.floor ? `, Level ${supplier.floor}` : ''}`;
  const pickupNotes = supplier.pickup_instructions;
  // Recomputed on each render, so options drop out as closing time nears.
  const choices = deadlineChoices(supplier.closes_at);
  const chosenDeadline = effectiveDeadline(choices, deadline);
  const closingMessage = closingNotice(supplier.closes_at, choices);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    if (!items.trim() || !deliveryLocation.trim()) {
      setErrorMsg('Please fill in required fields.');
      return;
    }

    if (!chosenDeadline) {
      setErrorMsg(closingMessage);
      return;
    }

    // When the balance could not be loaded, Order Service still decides: the
    // request waits until the credit is reserved, or is rejected if too low.
    if (!balanceUnknown && availableCredits < 1) {
      setErrorMsg('Insufficient credit balance (Requires 1 credit).');
      return;
    }

    setErrorMsg('');
    setSubmitting(true);
    try {
      await onSubmitOrder({
        supplierId: supplier.id,
        supplierName: supplier.name,
        pickupLocation,
        items: items.trim(),
        deliveryLocation: deliveryLocation.trim(),
        instructions: instructions.trim() || 'None',
        deadline: chosenDeadline.label,
        creditsReward: 1
      });

      setItems('');
      setDeliveryLocation('');
      setInstructions('');
      onClose();
    } catch (error) {
      setErrorMsg(error.message || 'Could not create this request.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={() => { if (!submitting) onClose(); }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create Errand Request</h3>
          <button className="btn btn-secondary btn-sm" onClick={onClose} disabled={submitting}>X</button>
        </div>

        {errorMsg && (
          <div className="notice-box" style={{ borderColor: '#DC2626', color: '#DC2626' }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="card" style={{ background: '#F8F8F8', marginBottom: '10px' }}>
            <div><strong>Supplier:</strong> {supplier.name}</div>
            <div><strong>Pickup Location:</strong> {pickupLocation}</div>
            {supplier.location_description ? (
              <div><strong>Pickup Directions:</strong> {supplier.location_description}</div>
            ) : null}
            {pickupNotes ? (
              <div><strong>Pickup Notes:</strong> {pickupNotes}</div>
            ) : null}
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
              placeholder="e.g. COM3 Level 1, outside the lift lobby"
              value={deliveryLocation}
              onChange={(e) => setDeliveryLocation(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Delivery Instructions</label>
            <input
              type="text"
              placeholder="e.g. Call me on arrival, or leave it at the reception counter"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label>Acceptance deadline</label>
            <select
              value={chosenDeadline?.label ?? ''}
              onChange={(e) => setDeadline(e.target.value)}
              disabled={!chosenDeadline}
            >
              {!chosenDeadline && <option value="">No time left today</option>}
              {choices.map((choice) => (
                <option key={choice.label} value={choice.label} disabled={!choice.available}>
                  {choice.label}{choice.available ? '' : ' (past closing)'}
                </option>
              ))}
            </select>
            {closingMessage && <p className="form-hint">{closingMessage}</p>}
          </div>

          <div className="notice-box">
            {balanceUnknown
              ? 'Credit Reservation: 1 Credit will be held once your balance can be checked. Your balance is temporarily unavailable.'
              : `Credit Reservation: 1 Credit will be held from available balance (${availableCredits} available).`}
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={submitting || !chosenDeadline}>
              {submitting ? 'Submitting...' : 'Submit Request'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
