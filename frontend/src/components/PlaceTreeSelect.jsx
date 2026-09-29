import React, { useEffect, useId, useMemo, useRef, useState } from "react";

const compareNames = (left, right) => left.name.localeCompare(right.name, "en", {
  sensitivity: "base",
  numeric: true,
});

/** A searchable place picker that keeps parents selectable while nesting children. */
export default function PlaceTreeSelect({
  places,
  value,
  onChange,
  emptyValue = "",
  emptyLabel = "Select a location…",
  ariaLabel = "Choose a location",
  id,
  disabled = false,
  className = "",
}) {
  const generatedId = useId();
  const panelId = `${id || generatedId}-place-tree`;
  const containerRef = useRef(null);
  const searchRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState(() => new Set());

  const model = useMemo(() => {
    const byId = new Map(places.map((place) => [place.id, place]));
    const children = new Map(places.map((place) => [place.id, []]));
    const roots = [];

    places.forEach((place) => {
      if (place.parent_id && byId.has(place.parent_id) && place.parent_id !== place.id) {
        children.get(place.parent_id).push(place);
      } else {
        roots.push(place);
      }
    });
    roots.sort(compareNames);
    children.forEach((items) => items.sort(compareNames));

    const pathCache = new Map();
    const pathFor = (placeId, visiting = new Set()) => {
      if (pathCache.has(placeId)) return pathCache.get(placeId);
      const place = byId.get(placeId);
      if (!place) return [];
      if (visiting.has(placeId)) return [place.name];
      const nextVisiting = new Set(visiting).add(placeId);
      const parentPath = place.parent_id ? pathFor(place.parent_id, nextVisiting) : [];
      const path = [...parentPath, place.name];
      pathCache.set(placeId, path);
      return path;
    };

    const ancestorIds = (placeId) => {
      const ids = [];
      const seen = new Set();
      let current = byId.get(placeId);
      while (current?.parent_id && byId.has(current.parent_id) && !seen.has(current.parent_id)) {
        seen.add(current.parent_id);
        ids.push(current.parent_id);
        current = byId.get(current.parent_id);
      }
      return ids;
    };

    return { byId, children, roots, pathFor, ancestorIds };
  }, [places]);

  const selectedLabel = value === emptyValue
    ? emptyLabel
    : model.byId.has(value)
      ? model.pathFor(value).join(" › ")
      : "Selected location unavailable";

  const visibleIds = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return null;
    const visible = new Set();
    places.forEach((place) => {
      const path = model.pathFor(place.id).join(" ").toLocaleLowerCase();
      if (path.includes(needle)) {
        visible.add(place.id);
        model.ancestorIds(place.id).forEach((ancestorId) => visible.add(ancestorId));
      }
    });
    return visible;
  }, [model, places, search]);

  useEffect(() => {
    if (!open) return undefined;
    setExpanded((current) => {
      const next = new Set(current);
      model.ancestorIds(value).forEach((idToExpand) => next.add(idToExpand));
      return next;
    });
    searchRef.current?.focus();

    const closeOnOutsideClick = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [model, open, value]);

  const choose = (nextValue) => {
    onChange(nextValue);
    setOpen(false);
    setSearch("");
  };

  const toggle = (placeId) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(placeId)) next.delete(placeId);
      else next.add(placeId);
      return next;
    });
  };

  const renderPlace = (place, depth = 0, lineage = new Set()) => {
    if (lineage.has(place.id) || (visibleIds && !visibleIds.has(place.id))) return null;
    const childPlaces = model.children.get(place.id) || [];
    const hasChildren = childPlaces.length > 0;
    const isExpanded = Boolean(search.trim()) || expanded.has(place.id);
    const nextLineage = new Set(lineage).add(place.id);
    return (
      <React.Fragment key={place.id}>
        <div className="place-tree-row" role="treeitem" aria-level={depth + 1}
             aria-expanded={hasChildren ? isExpanded : undefined}
             style={{ paddingLeft: `${8 + depth * 20}px` }}>
          {hasChildren ? (
            <button
              type="button"
              className="place-tree-toggle"
              aria-label={`${isExpanded ? "Collapse" : "Expand"} ${place.name}`}
              onClick={() => toggle(place.id)}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : <span className="place-tree-toggle-spacer" />}
          <button
            type="button"
            className={`place-tree-option${value === place.id ? " is-selected" : ""}`}
            onClick={() => choose(place.id)}
          >
            {place.name}
          </button>
        </div>
        {hasChildren && isExpanded
          ? childPlaces.map((child) => renderPlace(child, depth + 1, nextLineage))
          : null}
      </React.Fragment>
    );
  };

  return (
    <div ref={containerRef} className={`place-tree-select ${className}`.trim()}>
      <button
        id={id}
        type="button"
        className="place-tree-trigger"
        disabled={disabled}
        aria-label={ariaLabel}
        aria-haspopup="tree"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selectedLabel}</span>
        <span aria-hidden="true">{open ? "▴" : "▾"}</span>
      </button>
      {open ? (
        <div id={panelId} className="place-tree-panel">
          <input
            ref={searchRef}
            className="place-tree-search"
            type="search"
            placeholder="Search locations…"
            aria-label="Search locations"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="place-tree-options" role="tree" aria-label={ariaLabel}>
            <button
              type="button"
              className={`place-tree-empty-option${value === emptyValue ? " is-selected" : ""}`}
              onClick={() => choose(emptyValue)}
            >
              {emptyLabel}
            </button>
            {model.roots.map((place) => renderPlace(place))}
            {visibleIds?.size === 0 ? (
              <div className="place-tree-no-results">No locations found.</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
