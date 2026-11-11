import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

const raw = readFileSync(fileURLToPath(new URL('../src/utils/serviceWorker.js', import.meta.url)), 'utf8');

function setup({ waiting = true, registrationExists = true, updateOnRequest = false } = {}) {
  const source = raw
    .replace(/\bexport (const|async function|function)\b/g, '$1')
    .replace(/12 \* 1000/g, '45')
    .concat('\n;globalThis.testAPI = { applyPendingUpdate, registerServiceWorker, onReleasePublished, onCacheRefreshPublished, consumeAppliedUpdateReceipt, isPortalUpdateActive, setPortalUpdateActivity };');

  const worker = new EventTarget();
  worker.state = 'installed';
  worker.postMessage = () => {};
  const sw = new EventTarget();
  sw.controller = {};
  sw.register = async () => registration;
  sw.getRegistration = async () => registrationExists ? registration : undefined;
  const registration = new EventTarget();
  registration.waiting = waiting ? worker : null;
  registration.installing = null;
  let updateCalls = 0;
  registration.update = async () => {
    updateCalls++;
    if (updateOnRequest) {
      registration.installing = worker;
      registration.dispatchEvent(new Event('updatefound'));
      queueMicrotask(() => {
        registration.waiting = worker;
        worker.dispatchEvent(new Event('statechange'));
      });
    }
  };
  let reloads = 0;
  let notifications = 0;
  const noticeKinds = [];
  const window = new EventTarget();
  const saved = new Map();
  window.sessionStorage = {
    setItem(key, value) { saved.set(key, value); },
    getItem(key) { return saved.get(key) || null; },
    removeItem(key) { saved.delete(key); },
  };
  window.location = { reload() { reloads++; } };
  window.addEventListener('faipco-update-ready', (event) => { notifications++; noticeKinds.push(event.detail?.kind); });
  const document = new EventTarget();
  document.readyState = 'complete';
  document.visibilityState = 'visible';
  const timers = [];
  const context = {
    navigator: { serviceWorker: sw }, window, document,
    setTimeout, clearTimeout,
    setInterval(fn, ms) { timers.push(ms); }, clearInterval() {},
    console, Date, AbortController,
    CustomEvent: class extends Event { constructor(type, options = {}) { super(type); this.detail = options.detail; } },
    __APP_BUILD__: 'build-old',
    fetch() { throw Error('periodic version.json fetch is forbidden'); },
  };
  runInNewContext(source, context);
  return {
    ...context.testAPI, worker, sw, registration, document, window, saved,
    get reloads() { return reloads; },
    get updates() { return updateCalls; },
    get notifications() { return notifications; },
    get noticeKinds() { return noticeKinds; },
    get timers() { return timers; },
  };
}

async function flush() { await new Promise((resolve) => setImmediate(resolve)); }

test('no periodic polling; existing fully installed waiting worker triggers a prompt', async () => {
  const s = setup();
  s.registerServiceWorker();
  await flush();
  assert.equal(s.notifications, 1);
  assert.deepEqual(s.timers, []);
  assert.equal(s.updates, 0);
});

test('a release event NEVER announces until a new worker is installed and waiting', async () => {
  const s = setup({ waiting: false, updateOnRequest: false });
  s.registerServiceWorker();
  await flush();
  s.onReleasePublished('build-new');
  await flush();
  assert.equal(s.updates, 1);
  assert.equal(s.notifications, 0);
  assert.equal(s.reloads, 0);
});

test('server release event triggers SW check; installed worker announces once', async () => {
  const s = setup({ waiting: false, updateOnRequest: true });
  s.registerServiceWorker();
  await flush();
  s.onReleasePublished('build-new');
  await flush();
  assert.equal(s.updates, 1);
  assert.equal(s.notifications, 1);
  assert.equal(s.reloads, 0);
  s.onReleasePublished('build-new');
  await flush();
  assert.equal(s.notifications, 1);
});

test('same build and invalid build events are ignored', async () => {
  const s = setup({ waiting: false });
  s.registerServiceWorker();
  await flush();
  s.onReleasePublished('build-old');
  s.onReleasePublished('../hack');
  s.onReleasePublished(null);
  await flush();
  assert.equal(s.notifications, 0);
  assert.equal(s.updates, 0);
});

test('ready update activates by consent and reloads without removing caches', async () => {
  const s = setup();
  s.worker.postMessage = ({type}) => {
    assert.equal(type, 'SKIP_WAITING');
    queueMicrotask(() => { s.sw.controller = s.worker; s.sw.dispatchEvent(new Event('controllerchange')); });
  };
  const result = await s.applyPendingUpdate();
  assert.equal(result.ok, true);
  assert.equal(s.reloads, 1);
});

test('no waiting worker yields immediate retryable error, not an endless loader', async () => {
  const s = setup({ waiting: false });
  const result = await s.applyPendingUpdate();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'not-ready');
  assert.equal(s.reloads, 0);
});

test('controller change without consent never reloads an unsaved form', async () => {
  const s = setup();
  s.registerServiceWorker();
  await flush();
  s.sw.dispatchEvent(new Event('controllerchange'));
  assert.equal(s.reloads, 0);
});


test('manual cache-refresh is detected on same build; notice only after the worker is installed', async () => {
  const s = setup({ waiting: false, updateOnRequest: false });
  s.registerServiceWorker();
  await flush();
  s.onCacheRefreshPublished('20261111121212123456');
  await flush();
  assert.equal(s.updates, 1);
  assert.equal(s.notifications, 0);
  assert.equal(s.reloads, 0);
});

test('manual cache-refresh issues a distinct refresh notice, even with unchanged build', async () => {
  const s = setup({ waiting: false, updateOnRequest: true });
  s.registerServiceWorker();
  await flush();
  s.onCacheRefreshPublished('20261111121212123456');
  await flush();
  assert.equal(s.updates, 1);
  assert.equal(s.notifications, 1);
  assert.deepEqual(s.noticeKinds, ['cache_refresh']);
  s.onCacheRefreshPublished('20261111121212123456');
  await flush();
  assert.equal(s.notifications, 1);
});

test('invalid cache-refresh stamp is ignored', async () => {
  const s = setup({ waiting: false });
  s.registerServiceWorker();
  await flush();
  s.onCacheRefreshPublished('../hijack');
  s.onCacheRefreshPublished('');
  s.onCacheRefreshPublished(null);
  await flush();
  assert.equal(s.updates, 0);
});


test('tap immediately starts an update activity, displays phases, and saves a one-time completion receipt', async () => {
  const s = setup();
  const phases = [];
  s.worker.postMessage = () => {
    queueMicrotask(() => { s.sw.controller = s.worker; s.sw.dispatchEvent(new Event('controllerchange')); });
  };
  const pending = s.applyPendingUpdate({ onPhase: (phase) => phases.push(phase) });
  await flush();
  assert.equal(s.isPortalUpdateActive(), true);
  const result = await pending;
  assert.equal(result.ok, true);
  assert.equal(s.reloads, 1);
  assert.deepEqual(phases, ['activating', 'reloading']);
  assert.equal(s.consumeAppliedUpdateReceipt(), 'release');
  assert.equal(s.consumeAppliedUpdateReceipt(), null);
});

test('cache refresh success is reported distinctly from a new release', async () => {
  const s = setup({ waiting: false, updateOnRequest: true });
  s.registerServiceWorker();
  await flush();
  s.onCacheRefreshPublished('20261111121212123456');
  await flush();
  s.worker.postMessage = () => {
    queueMicrotask(() => { s.sw.controller = s.worker; s.sw.dispatchEvent(new Event('controllerchange')); });
  };
  assert.equal((await s.applyPendingUpdate()).ok, true);
  assert.equal(s.consumeAppliedUpdateReceipt(), 'cache_refresh');
});

test('missing worker and activation timeout never leave the app flagged as updating', async () => {
  const noWorker = setup({ waiting: false });
  assert.equal((await noWorker.applyPendingUpdate()).reason, 'not-ready');
  assert.equal(noWorker.isPortalUpdateActive(), false);
  const timeout = setup();
  assert.equal((await timeout.applyPendingUpdate()).reason, 'activation-timeout');
  assert.equal(timeout.isPortalUpdateActive(), false);
  assert.equal(timeout.reloads, 0);
  assert.equal(timeout.consumeAppliedUpdateReceipt(), null);
});

test('server deployment activity can be tracked independently of the SW handoff', () => {
  const s = setup();
  s.setPortalUpdateActivity('server-deployment', true);
  assert.equal(s.isPortalUpdateActive(), true);
  s.setPortalUpdateActivity('sw-activation', true);
  s.setPortalUpdateActivity('server-deployment', false);
  assert.equal(s.isPortalUpdateActive(), true);
  s.setPortalUpdateActivity('sw-activation', false);
  assert.equal(s.isPortalUpdateActive(), false);
});
