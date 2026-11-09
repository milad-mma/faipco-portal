import test from 'node:test';
import assert from 'node:assert/strict';
import { clearApiCache, setCacheOwner, swrAbortable } from '../src/api/swrCache.js';

const tick = () => new Promise((resolve) => setImmediate(resolve));

test('shares requests and aborts only after the last subscriber leaves', async () => {
  setCacheOwner('photo-test-1');
  let fetchCount = 0;
  let abortCount = 0;
  let finish;
  const fetcher = (signal) => {
    fetchCount++;
    signal.addEventListener('abort', () => { abortCount++; }, { once: true });
    return new Promise((resolve) => { finish = resolve; });
  };
  const a = new AbortController();
  const b = new AbortController();
  const received = [];
  const pa = swrAbortable('photo:1', fetcher, (x) => received.push(['a', x]), { signal: a.signal });
  const pb = swrAbortable('photo:1', fetcher, (x) => received.push(['b', x]), { signal: b.signal });
  await tick();
  assert.equal(fetchCount, 1);
  a.abort();
  assert.equal(abortCount, 0);
  finish('photo-blob');
  await Promise.all([pa, pb]);
  assert.deepEqual(received, [['b', 'photo-blob']]);
  assert.equal(abortCount, 0);
  clearApiCache();
});

test('cancels network after all subscribers leave and does not cache cancelled result', async () => {
  setCacheOwner('photo-test-2');
  let aborted = 0;
  let finish;
  const fetcher = (signal) => {
    signal.addEventListener('abort', () => aborted++, { once: true });
    return new Promise((resolve) => { finish = resolve; });
  };
  const c = new AbortController();
  const p = swrAbortable('photo:2', fetcher, () => assert.fail('cancelled callback'), { signal: c.signal });
  await tick();
  c.abort();
  assert.equal(aborted, 1);
  finish('stale');
  await p;
  let refetch = 0;
  const fresh = await swrAbortable('photo:2', async () => { refetch++; return 'new'; }, () => {}, { maxAgeMs: 60_000 });
  assert.equal(fresh, 'new');
  assert.equal(refetch, 1);
  clearApiCache();
});

test('changing authenticated owner cancels pending binary request and clears cache', async () => {
  setCacheOwner('photo-test-3');
  let aborted = false;
  let finish;
  const p = swrAbortable('photo:3', (signal) => {
    signal.addEventListener('abort', () => { aborted = true; }, { once: true });
    return new Promise((resolve) => { finish = resolve; });
  }, () => assert.fail('old user must not receive callback'));
  await tick();
  setCacheOwner('photo-test-4');
  assert.equal(aborted, true);
  finish('old-user-photo');
  await p;
  let fetched = false;
  await swrAbortable('photo:3', async () => { fetched = true; return 'new-user-photo'; }, () => {});
  assert.equal(fetched, true);
  clearApiCache();
});
