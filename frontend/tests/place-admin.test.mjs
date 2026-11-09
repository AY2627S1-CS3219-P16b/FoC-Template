import test from 'node:test';
import assert from 'node:assert/strict';
import { deletePlace, renamePlace } from '../src/api/suppliers.js';

test('rename and delete send the admin reason, and only a name on rename', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (url, options) => {
      calls.push({ url, ...options });
      return new Response(JSON.stringify({ id: 'p1', name: 'The Terrace' }), { status: 200 });
    };
    await renamePlace({ token: 't', placeId: 'p1', name: 'The Terrace', reason: 'official name' });
    await deletePlace({ token: 't', placeId: 'p1', reason: 'closed down' });

    assert.equal(calls[0].method, 'PATCH');
    assert.match(calls[0].url, /\/api\/v1\/places\/p1$/);
    assert.deepEqual(JSON.parse(calls[0].body), { name: 'The Terrace' });
    assert.equal(calls[0].headers['X-Admin-Reason'], 'official name');

    assert.equal(calls[1].method, 'DELETE');
    assert.match(calls[1].url, /\/api\/v1\/places\/p1$/);
    assert.equal(calls[1].body, undefined);
    assert.equal(calls[1].headers['X-Admin-Reason'], 'closed down');
  } finally { globalThis.fetch = originalFetch; }
});

test('a location still in use explains what blocks the delete', async () => {
  const originalFetch = globalThis.fetch;
  const detail = 'This location still has 2 suppliers (including ones hidden from browsing). Move or remove them first.';
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail }), { status: 409 });
    await assert.rejects(
      () => deletePlace({ token: 't', placeId: 'p1', reason: 'cleanup' }),
      (error) => error.status === 409 && error.message === detail,
    );
  } finally { globalThis.fetch = originalFetch; }
});
