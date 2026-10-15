import React, { useEffect, useRef, useState } from "react";

// Supplier cards show photos at this shape; the service crops uploads to it.
const CARD_RATIO = 16 / 9;

const clamp = (value) => Math.min(1, Math.max(0, value));

/**
 * Lets an admin choose which part of a photo the supplier card shows.
 *
 * The preview is card-shaped and uses object-fit: cover with a percentage
 * object-position. A percentage there means "this fraction of the spare room
 * sits before the visible part", which is exactly how the service crops with
 * `focus`, so the saved photo matches the preview pixel for pixel.
 */
export default function PhotoCropper({ file, busy, onConfirm, onCancel }) {
  const [src, setSrc] = useState("");
  const [size, setSize] = useState(null);
  const [focus, setFocus] = useState(0.5);
  const frameRef = useRef(null);
  const dragRef = useRef(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    setSize(null);
    setFocus(0.5);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Which way the photo has room to move inside the card's shape.
  const axis = !size ? null
    : size.width / size.height < CARD_RATIO - 0.01 ? "vertical"
      : size.width / size.height > CARD_RATIO + 0.01 ? "horizontal"
        : null;

  /** Spare room, in on-screen pixels, along the axis the photo can move. */
  const spareRoom = () => {
    const box = frameRef.current.getBoundingClientRect();
    return axis === "vertical"
      ? box.width * (size.height / size.width) - box.height
      : box.height * (size.width / size.height) - box.width;
  };

  const startDrag = (event) => {
    if (!axis || busy) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, focus, room: spareRoom() };
  };

  const drag = (event) => {
    const start = dragRef.current;
    if (!start || start.room <= 0) return;
    // Dragging the photo down reveals more of its top, so focus goes down.
    const moved = axis === "vertical" ? event.clientY - start.y : event.clientX - start.x;
    setFocus(clamp(start.focus - moved / start.room));
  };

  const endDrag = () => { dragRef.current = null; };

  const percent = `${Math.round(focus * 1000) / 10}%`;
  const position = axis === "horizontal" ? `${percent} 50%` : `50% ${percent}`;

  return (
    <div className="photo-cropper">
      <div
        ref={frameRef}
        className={`photo-cropper-frame${axis ? " is-draggable" : ""}`}
        onPointerDown={startDrag}
        onPointerMove={drag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        {src && (
          <img
            src={src}
            alt="How the supplier card will show this photo"
            draggable={false}
            style={{ objectPosition: position }}
            onLoad={(event) => setSize({
              width: event.currentTarget.naturalWidth,
              height: event.currentTarget.naturalHeight,
            })}
          />
        )}
      </div>
      {axis ? (
        <label className="photo-cropper-slider">
          <small>{axis === "vertical" ? "Top" : "Left"}</small>
          <input
            type="range"
            min="0"
            max="100"
            value={Math.round(focus * 100)}
            disabled={busy}
            aria-label="Which part of the photo the card shows"
            onChange={(event) => setFocus(Number(event.target.value) / 100)}
          />
          <small>{axis === "vertical" ? "Bottom" : "Right"}</small>
        </label>
      ) : null}
      <small>
        {axis
          ? "Drag the photo or use the slider to frame the shop sign. This is exactly how the card will show it."
          : "This is how the card will show the photo."}
      </small>
      <div className="photo-cropper-actions">
        <button type="button" className="btn btn-sm btn-primary"
                disabled={busy || !size} onClick={() => onConfirm(focus)}>
          {busy ? "Uploading…" : "Use this photo"}
        </button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
