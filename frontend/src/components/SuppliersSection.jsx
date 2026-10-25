import React, { useEffect, useRef, useState } from 'react';
import {
  DEFAULT_SORT,
  canRetrySupplierRequest,
  SUPPLIER_CATEGORIES,
  SUPPLIER_SORTS,
  fetchPlaces,
  fetchSuppliers,
  formatHours,
  formatPlace,
  supplierImageSrc,
} from '../api/suppliers';
import PlaceTreeSelect from './PlaceTreeSelect';
import Icon from './Icon';

const PAGE_SIZE = 12;
const SEARCH_DEBOUNCE_MS = 300;

/** "Wok Express" → "WE", so a card without a photo still has a visual anchor. */
const initials = (name) => name.split(/\s+/).filter((word) => /[A-Za-z0-9]/.test(word))
  .slice(0, 2).map((word) => word.match(/[A-Za-z0-9]/)[0].toUpperCase()).join('');

/**
 * The supplier's photo, or a tile with its initials when there is none or it
 * fails to load, so every card in the grid keeps the same shape.
 */
export function SupplierImage({ supplier }) {
  const [failed, setFailed] = useState(false);
  const src = supplierImageSrc(supplier.image_url);
  if (!src || failed) {
    return (
      <div className={`supplier-image supplier-image-placeholder category-${supplier.supplier_type}`}
           aria-hidden="true">
        {initials(supplier.name)}
      </div>
    );
  }
  return (
    <img className="supplier-image" src={src} alt={supplier.name}
         loading="lazy" decoding="async" onError={() => setFailed(true)} />
  );
}

/** Current filters from the address bar, so a shared or refreshed link restores them. */
const urlParam = (key, fallback = '') =>
  new URLSearchParams(window.location.search).get(key) || fallback;

export default function SuppliersSection({ token, onQuickOpenModal }) {
  const [searchTerm, setSearchTerm] = useState(() => urlParam('q'));
  const [debouncedSearch, setDebouncedSearch] = useState(() => urlParam('q'));
  const [selectedCategory, setSelectedCategory] = useState(() => urlParam('type', 'ALL'));
  const [selectedPlace, setSelectedPlace] = useState(() => urlParam('place', 'ALL'));
  const [sort, setSort] = useState(() => urlParam('sort', DEFAULT_SORT));
  const [page, setPage] = useState(() => Number(urlParam('page', '1')) || 1);

  const [places, setPlaces] = useState([]);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [placesError, setPlacesError] = useState(null);
  const [retry, setRetry] = useState(0);

  // Wait for a pause in typing so each keystroke does not hit the service.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // A narrowed result set may have fewer pages than the one being viewed.
  // Skipped on mount so a page number restored from the URL survives.
  const isInitialRender = useRef(true);
  useEffect(() => {
    if (isInitialRender.current) {
      isInitialRender.current = false;
      return;
    }
    setPage(1);
  }, [debouncedSearch, selectedCategory, selectedPlace]);

  // Mirror the active filters into the address bar without reloading, so the
  // view can be bookmarked or shared. replaceState keeps typing out of history.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const apply = (key, value) => (value ? params.set(key, value) : params.delete(key));
    apply('q', debouncedSearch.trim());
    apply('type', selectedCategory === 'ALL' ? '' : selectedCategory);
    apply('place', selectedPlace === 'ALL' ? '' : selectedPlace);
    apply('sort', sort === DEFAULT_SORT ? '' : sort);
    apply('page', page > 1 ? String(page) : '');
    window.history.replaceState(null, '', `?${params}`);
  }, [debouncedSearch, selectedCategory, selectedPlace, sort, page]);

  useEffect(() => {
    if (!token) return undefined;
    let ignore = false;
    fetchPlaces({ token })
      .then((rows) => {
        if (!ignore) { setPlaces(rows); setPlacesError(null); }
      })
      .catch((requestError) => {
        if (!ignore) { setPlaces([]); setPlacesError(requestError); }
      });
    return () => {
      ignore = true;
    };
  }, [token, retry]);

  useEffect(() => {
    if (!token) return undefined;
    let ignore = false;
    setIsLoading(true);
    fetchSuppliers({
      token,
      search: debouncedSearch,
      category: selectedCategory,
      place: selectedPlace,
      sort,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (ignore) return;
        setResult(data);
        setError(null);
      })
      .catch((requestError) => {
        if (ignore) return;
        setResult(null);
        setError(requestError);
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });
    // Discard a slow response if the filters changed while it was in flight.
    return () => {
      ignore = true;
    };
  }, [token, debouncedSearch, selectedCategory, selectedPlace, sort, page, retry]);

  const suppliers = result?.items ?? [];
  const totalPages = result?.total_pages ?? 0;
  const hasActiveFilters =
    Boolean(searchTerm) || selectedCategory !== 'ALL' || selectedPlace !== 'ALL'
    || sort !== DEFAULT_SORT || page !== 1;

  const clearFilters = () => {
    setSearchTerm('');
    setDebouncedSearch('');
    setSort(DEFAULT_SORT);
    setSelectedCategory('ALL');
    setSelectedPlace('ALL');
    setPage(1);
  };

  return (
    <section>
      <div className="section-header compact-heading">
        <h2>Suppliers &amp; Campus Facilities</h2>
        {result ? (
          <span className="section-count">{result.total} suppliers</span>
        ) : null}
      </div>

      <div className="filter-bar supplier-filters">
        <div className="search-field">
        <Icon name="search" />
        <input
          type="search"
          className="search-input"
          aria-label="Search suppliers or places"
          placeholder="Search suppliers or places, e.g. coffee, COM3…"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
        </div>
        <select
          className="filter-select"
          value={selectedCategory}
          onChange={(event) => setSelectedCategory(event.target.value)}
          aria-label="Filter by category"
        >
          <option value="ALL">All Categories</option>
          {selectedCategory !== 'ALL' && !SUPPLIER_CATEGORIES.some((c) => c.value === selectedCategory) ? (
            <option value={selectedCategory} disabled>Unavailable category</option>
          ) : null}
          {SUPPLIER_CATEGORIES.map((category) => (
            <option key={category.value} value={category.value}>
              {category.label}
            </option>
          ))}
        </select>
        <PlaceTreeSelect
          places={places}
          value={places.find((p) => p.id === selectedPlace || p.search_key === selectedPlace)?.id || selectedPlace}
          onChange={setSelectedPlace}
          emptyValue="ALL"
          emptyLabel="All Locations"
          ariaLabel="Filter by location"
          className="filter-place-tree"
        />
        <select
          className="filter-select"
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          aria-label="Sort results"
        >
          {!SUPPLIER_SORTS.some((option) => option.value === sort) ? (
            <option value={sort} disabled>Unavailable sorting option</option>
          ) : null}
          {SUPPLIER_SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              Sort: {option.label}
            </option>
          ))}
        </select>
        {hasActiveFilters ? (
          <button type="button" className="btn btn-secondary" onClick={clearFilters}>
            Clear filters
          </button>
        ) : null}
      </div>

      {placesError && !error ? (
        <div className="notice-box" role="alert">
          <p>{placesError.message} You can still search or browse suppliers.</p>
          {canRetrySupplierRequest(placesError) ? (
            <button type="button" className="btn" onClick={() => setRetry((n) => n + 1)}>Try again</button>
          ) : null}
        </div>
      ) : null}
      {error ? (
        <div className="empty-state" role="alert">
          <p>{error.message}</p>
          {canRetrySupplierRequest(error) ? (
            <button type="button" className="btn" disabled={isLoading} onClick={() => setRetry((n) => n + 1)}>
              {isLoading ? 'Trying again…' : 'Try again'}
            </button>
          ) : null}
        </div>
      ) : isLoading && !result ? (
        <div className="empty-state">
          <p>Loading suppliers...</p>
        </div>
      ) : suppliers.length > 0 ? (
        <>
          <div className="grid-suppliers">
            {suppliers.map((supplier) => (
              <article key={supplier.id} className="card supplier-card">
                <div className="supplier-media">
                  <SupplierImage key={supplier.image_url} supplier={supplier} />
                  {typeof supplier.is_open_now === 'boolean' && (
                    <span className={`supplier-status ${supplier.is_open_now ? 'supplier-status-open' : 'supplier-status-closed'}`}>
                      {supplier.is_open_now ? 'Open now' : 'Closed'}
                    </span>
                  )}
                </div>
                <div className="supplier-card-content">
                <p className="supplier-category">{SUPPLIER_CATEGORIES.find((category) => category.value === supplier.supplier_type)?.label || 'Campus supplier'}</p>
                <div className="supplier-card-header">
                  <h3 className="supplier-name"><a href={`?screen=supplier-detail&supplier_id=${encodeURIComponent(supplier.id)}`}>{supplier.name}</a></h3>
                </div>
                <div className="supplier-info supplier-meta"><Icon name="pin" /><span>{formatPlace(supplier.place)}{supplier.floor ? ` · Level ${supplier.floor}` : ''}</span></div>
                <div className="supplier-info supplier-meta"><Icon name="clock" /><span>{formatHours(supplier) || 'Opening hours not listed'}</span></div>
                  {supplier.tags?.length > 0 ? (
                    <ul className="supplier-tags" aria-label="Supplier tags">
                      {supplier.tags.map((tag) => (
                        <li key={tag} className="supplier-tag">{tag}</li>
                      ))}
                    </ul>
                  ) : null}
                <div className="supplier-card-actions">
                  <button
                    className="btn btn-primary btn-block"
                    onClick={() => onQuickOpenModal(supplier)}
                    disabled={!supplier.is_active || !supplier.is_open_now}
                  >
                    Create Request<Icon name="arrow" />
                  </button>
                </div>
                </div>
              </article>
            ))}
          </div>

          {totalPages > 1 ? (
            <div className="pagination">
              <button
                className="btn"
                onClick={() => setPage((current) => current - 1)}
                disabled={page <= 1 || isLoading}
              >
                Previous
              </button>
              <span className="pagination-status">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn"
                onClick={() => setPage((current) => current + 1)}
                disabled={page >= totalPages || isLoading}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="empty-state">
          <p>No suppliers found matching the criteria.</p>
          {hasActiveFilters ? (
            <button type="button" className="btn btn-secondary" onClick={clearFilters}>
              Clear filters
            </button>
          ) : null}
        </div>
      )}
    </section>
  );
}
