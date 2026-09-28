import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchSuppliers, fetchSupplier, fetchPlaces, supplierErrorMessage, canRetrySupplierRequest } from '../src/api/suppliers.js';

test('supplier requests translate HTTP failures instead of exposing backend text', async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const [request, status, body, expected] of [
      [() => fetchSuppliers({category: 'PRINTER'}), 422, {detail: 'supplier_type must be one of FOOD_BEVERAGE, RETAIL, FACILITY'}, /category isn't available/],
      [() => fetchSuppliers(), 422, {detail: [{loc: ['query', 'page'], msg: 'technical validation'}]}, /page link isn't valid/],
      [() => fetchSuppliers(), 422, {detail: 'Invalid place name.'}, /location isn't valid/],
      [() => fetchSupplier({supplierId: 'missing'}), 404, {detail: 'Supplier not found.'}, /supplier is no longer available/],
      [() => fetchPlaces({}), 503, {detail: 'SQL connection internal details'}, /temporarily unavailable/],
    ]) {
      globalThis.fetch = async () => new Response(JSON.stringify(body), {status});
      await assert.rejects(request, (error) => {
        assert.equal(error.status, status);
        assert.match(error.message, expected);
        assert.doesNotMatch(error.message, /FOOD_BEVERAGE|technical validation|SQL connection|\[object Object\]/);
        return true;
      });
    }
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
    await assert.rejects(() => fetchSuppliers(), /Check your connection/);
  } finally { globalThis.fetch = originalFetch; }
});

test('authentication, unknown errors, and remaining invalid filters have actionable text', () => {
  assert.match(supplierErrorMessage(401), /log in again/);
  assert.match(supplierErrorMessage(403), /permission/);
  assert.match(supplierErrorMessage(429), /wait/);
  assert.match(supplierErrorMessage(422, {detail: 'sort must be one of name'}), /Sort menu/);
  assert.match(supplierErrorMessage(422, {detail: [{loc:['query','q']}]}), /200 characters/);
  assert.match(supplierErrorMessage(400, {detail: 'private internals'}), /try again/);
});

test('retry is available only for transient failures', () => {
  for (const status of [0, 408, 429, 500, 502, 503, 504]) {
    assert.equal(canRetrySupplierRequest({status}), true);
  }
  for (const status of [400, 401, 403, 404, 422, undefined]) {
    assert.equal(canRetrySupplierRequest({status}), false);
  }
  assert.equal(canRetrySupplierRequest(null), false);
});
