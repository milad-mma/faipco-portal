import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

// Exercise the actual worker, not a reimplementation of the session gate.
// Workbox, IndexedDB, Cache Storage and OS notification APIs are mocked;
// transactions execute in order and only commit on success.
const source = readFileSync(new URL('../src/sw.js', import.meta.url), 'utf8')
  .replace(/^import .*;\s*$/gm, '');

function fixture({ enabled = true, marker = 'session-A', fault = null, imageHook, showHook, receiptHook } = {}) {
  const stores = { meta: new Map([['enabled', enabled], ['sessionMarker', marker]]), seen: new Map(), pending: new Map() };
  const shown = [], messages = [], handlers = new Map();
  let tail = Promise.resolve();
  let closes = 0;
  const db = {
    close() { closes++; },
    transaction(name, mode) {
      const ops = [];
      const tx = { error: null, objectStore() {
        return {
          get(key) { const request = {}; ops.push(map => { request.result = map.get(key); request.onsuccess?.(); }); return request; },
          getAll() { const req = {}; ops.push(map => { req.result = [...map.values()]; }); return req; },
          put(value, key = value.id) { assert.equal(mode, 'readwrite'); ops.push(map => map.set(key, value)); return {}; },
          delete(key) { assert.equal(mode, 'readwrite'); ops.push(map => map.delete(key)); return {}; },
        };
      } };
      tail = tail.then(() => {
        if (name === 'meta' && mode === 'readonly' && (fault === 'abort' || fault === 'error')) {
          tx.error = new Error('mock storage failure');
          if (fault === 'abort') tx.onabort?.(); else tx.onerror?.();
          return;
        }
        const map = new Map(stores[name]);
        for (const op of ops) op(map);
        if (mode === 'readwrite') stores[name] = map;
        tx.oncomplete?.();
      });
      return tx;
    },
  };
  const registration = {
    async showNotification(title, options) {
      await showHook?.(stores);
      shown.push({ title, options, data: options.data, closed: false, close() { this.closed = true; } });
    },
    async getNotifications({ tag } = {}) { return shown.filter(n => !n.closed && (!tag || n.options.tag === tag)); },
  };
  const context = {
    AbortController, fetch: async (_, opts) => ({ status: receiptHook?.(JSON.parse(opts.body)) ?? 204 }),
    self: { location: { origin: "https://portal.test" }, __WB_MANIFEST: [], addEventListener(type, fn) { handlers.set(type, fn); }, registration,
      clients: { async openWindow() {}, async matchAll() { return [{ url: "https://portal.test", postMessage: msg => messages.push(msg) }]; }, },
    },
    indexedDB: { open() { const req = {}; queueMicrotask(() => {
      if (fault === 'open') { req.error = new Error('mock open failure'); req.onerror?.(); }
      else { req.result = db; req.onsuccess?.(); }
    }); return req; } },
    caches: { async open() { return { async match() { await imageHook?.(stores); return { ok: true, headers: { get: () => 'text/html' } }; } }; } },
    precacheAndRoute() {}, registerRoute() {}, createHandlerBoundToURL() { return () => {}; },
    NavigationRoute: class {}, NetworkOnly: class {}, console, setTimeout, clearTimeout,
  };
  runInNewContext(source, context, { filename: 'sw.js' });
  function dispatch(type, event) {
    let work;
    handlers.get(type)({ ...event, waitUntil(p) { work = p; } });
    return work;
  }
  return {
    click() { return dispatch("notificationclick", { notification: shown[0] }); },
    retry() { return dispatch("sync", { tag: "faipco-receipts" }); },
    shown, messages, stores, get closes() { return closes; },
    push(payload = {}) { return dispatch('push', { data: { json: () => ({ title: 'notice', session_marker: 'session-A', ...payload }) } }); },
    session(enabled, sessionMarker) { return dispatch('message', { data: { type: 'FAIPCO_PUSH_SESSION', enabled, sessionMarker } }); },
  };
}

test('matching active session displays a real notification and refreshes clients', async () => {
  const f = fixture(); await f.push();
  assert.equal(f.shown.length, 1); assert.equal(f.messages.length, 1); assert.ok(f.closes > 0);
  assert.equal(f.shown[0].options.dir, 'rtl');
});
for (const [name, options, payload] of [
  ['disabled', { enabled: false }, {}],
  ['no stored marker', { marker: null }, {}],
  ['different session', {}, { session_marker: 'session-B' }],
  ['legacy payload without marker', {}, { session_marker: undefined }],
  ['database open error', { fault: 'open' }, {}],
  ['transaction error', { fault: 'error' }, {}],
  ['transaction abort', { fault: 'abort' }, {}],
]) {
  test(`${name}: fail closed without notifying`, async () => {
    const f = fixture(options); await f.push(payload);
    assert.equal(f.shown.length, 0); assert.equal(f.messages.length, 0);
  });
}
test('logout closes visible notifications and blocks subsequent delivery; login enables new SID only', async () => {
  const f = fixture(); await f.push();
  await f.session(false, null); assert.equal(f.shown[0].closed, true);
  await f.push(); assert.equal(f.shown.length, 1);
  await f.session(true, 'session-B'); await f.push(); assert.equal(f.shown.length, 1);
  await f.push({ session_marker: 'session-B' }); assert.equal(f.shown.length, 2);
});
test('concurrent OA retries display once even if notification is later dismissed', async () => {
  const f = fixture(); const p = { notification_key: 'oa:letter:7:user:5' };
  await Promise.all([f.push(p), f.push(p)]); assert.equal(f.shown.length, 1);
  f.shown[0].close(); await f.push(p); assert.equal(f.shown.length, 1);
});
test('ordinary notices are not deduplicated by OA keys', async () => {
  const f = fixture(); await f.push(); await f.push(); assert.equal(f.shown.length, 2);
});
test('logout or account switch while loading icons prevents stale notification', async () => {
  const f = fixture({ imageHook(stores) { stores.meta.set('sessionMarker', 'session-B'); } });
  await f.push({ notification_key: 'oa:1' });
  assert.equal(f.shown.length, 0); assert.equal(f.messages.length, 0); assert.equal(f.stores.seen.size, 0);
});
test('a rejected showNotification does not permanently consume an OA key', async () => {
  let calls = 0;
  const f = fixture({ showHook() { if (++calls === 1) throw new Error('mock notification failure'); } });
  const p = { notification_key: 'oa:2' };
  await assert.rejects(f.push(p), /mock notification failure/);
  assert.equal(f.stores.seen.size, 0);
  await f.push(p); assert.equal(f.shown.length, 1);
});


test('session switch during OS display closes the stale notification without refreshing tabs', async () => {
  const f = fixture({ showHook(stores) { stores.meta.set('sessionMarker', 'session-B'); } });
  await f.push();
  assert.equal(f.shown.length, 1); assert.equal(f.shown[0].closed, true); assert.equal(f.messages.length, 0);
});

test('durable dispatch event is deduplicated on the same session', async () => {
  const f = fixture(); const p = { notification_key: 'dispatch:notice:269:publish' };
  await Promise.all([f.push(p), f.push(p)]);
  f.shown[0].close(); await f.push(p);
  assert.equal(f.shown.length, 1);
});
test('durable dispatch key does not suppress a newly registered session', async () => {
  const f = fixture(); const p = { notification_key: 'dispatch:notice:269:publish' };
  await f.push(p); await f.session(true, 'session-B');
  await f.push({...p, session_marker: 'session-B'});
  assert.equal(f.shown.length, 2);
});

test('device confirms only a displayed push and the click on that exact notification', async () => {
  const receipts = [];
  const f = fixture({ receiptHook: receipt => { receipts.push(receipt); } });
  await f.push({ receipt_token: 'token-A', notification_key: 'event-A' });
  await f.push({ receipt_token: 'token-B', session_marker: 'previous-login' });
  await f.click();
  assert.deepEqual(receipts, [{ token: 'token-A', action: 'received' }, { token: 'token-A', action: 'opened' }]);
  assert.equal(f.messages[0].receipt_token, undefined);
});

test('receipts survive a network failure and drain when connectivity returns', async () => {
  let online = false;
  const f = fixture({ receiptHook: () => { if (!online) throw new Error('offline'); } });
  await f.push({ receipt_token: 'token-A' });
  await f.click();
  assert.equal(f.stores.pending.size, 2);
  online = true;
  await f.retry();
  assert.equal(f.stores.pending.size, 0);
});
