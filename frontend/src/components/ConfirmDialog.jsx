import React, { useEffect, useRef } from "react";

/**
 * An in-app replacement for window.confirm, styled like the rest of the app.
 *
 * Focus starts on the cancel button, so pressing Enter by reflex keeps the
 * user's work; Escape or a click outside the dialog also cancels.
 */
export default function ConfirmDialog({
  title, message, confirmLabel, cancelLabel = "Cancel", onConfirm, onCancel,
}) {
  const cancelRef = useRef(null);
  // The latest handler, so a parent re-render does not re-run the effect
  // and pull focus back to the cancel button.
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") onCancelRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className="modal-content confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="confirm-dialog-title">{title}</h3>
        <p id="confirm-dialog-message">{message}</p>
        <div className="confirm-dialog-actions">
          <button ref={cancelRef} type="button" className="btn btn-sm btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="btn btn-sm btn-danger" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
