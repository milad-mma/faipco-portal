import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

const raw = readFileSync(fileURLToPath(new URL('../src/utils/serviceWorker.js', import.meta.url)), 'utf8');

function setup({ waiting = true, registrationExists = true } = {}) {
  const source = raw
    .replace(/\bexport (const|async function|function)\b/g, '$1')
    .replace(/12 \* 1000/g, '45')
    .concat('\n;globalThis.testAPI = { applyPendingUpdate, registerServiceWorker, checkDeployedVersion };');

  const worker = new EventTarget();
  worker.state = 'installed';
  worker.postMessage = () => {};
  const sw = new EventTarget();
  const old = {};
  sw.controller = old;
  sw.register = async () => registration;
  sw.getRegistration = async () => registrationExists ? registration : undefined;
  const registration = new EventTarget();
  registration.waiting = waiting ? worker : null;
  registration.installing = null;
  registration.update = async () => {};
  let reloads = 0;
  let cacheDeleted = false;
  let unregistered = false;
  registration.unregister = async () => { unregistered = true; };
  const window = new EventTarget();
  window.location = { reload() { reloads++; } };
  const document = new EventTarget();
  document.readyState = 'complete';
  document.visibilityState = 'visible';
  const context = {
    navigator: { serviceWorker: sw }, window, document,
    caches: { keys() { cacheDeleted = true; return []; } },
    setTimeout, clearTimeout, setInterval() {}, clearInterval() {},
    console, Date, AbortController, CustomEvent: class extends Event { constructor(type) { super(type); } },
    __APP_BUILD__: 'build-old',
    fetch: async () => ({ ok: true, json: async () => ({ build: 'build-old' }) }),
  };
  runInNewContext(source, context);
  return {
    ...context.testAPI, worker, sw, registration,
    get reloads() { return reloads; },
    get cacheDeleted() { return cacheDeleted; },
    get unregistered() { return unregistered; },
  };
}

test('ready update switches SW, then reloads; never removes caches or registration', async () => {
  const s = setup();
  s.worker.postMessage = ({type}) => {
    assert.equal(type, 'SKIP_WAITING');
    queueMicrotask(() => { s.sw.controller = s.worker; s.sw.dispatchEvent(new Event('controllerchange')); });
  };
  const result = await s.applyPendingUpdate();
  assert.equal(result.ok, true);
  assert.equal(s.reloads, 1);
  assert.equal(s.cacheDeleted, false);
  assert.equal(s.unregistered, false);
});

test('installation failure returns retryable error, without reload or cache deletion', async () => {
  const s = setup({ waiting: false });
  const result = await s.applyPendingUpdate();
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'install-timeout');
  assert.equal(s.reloads, 0);
  assert.equal(s.cacheDeleted, false);
  assert.equal(s.unregistered, false);
});

test('a worker arriving during update is activated normally', async () => {
  const s = setup({ waiting: false });
  s.registration.update = async () => {
    queueMicrotask(() => {
      s.registration.waiting = s.worker;
      s.worker.dispatchEvent(new Event('statechange'));
    });
  };
  s.registration.installing = s.worker;
  s.worker.postMessage = () => {
    queueMicrotask(() => { s.sw.controller = s.worker; s.sw.dispatchEvent(new Event('controllerchange')); });
  };
  const result = await s.applyPendingUpdate();
  assert.equal(result.ok, true);
  assert.equal(s.reloads, 1);
});

test('controller change without user confirmation does not reload a form', async () => {
  const s = setup();
  s.registerServiceWorker();
  await new Promise((resolve) => setImmediate(resolve));
  s.sw.dispatchEvent(new Event('controllerchange'));
  assert.equal(s.reloads, 0);
});

test('no registered worker: error is returned, login and stored data stay intact', async () => {
  const s = setup({ registrationExists: false });
  assert.equal((await s.applyPendingUpdate()).ok, false);
  assert.equal(s.reloads, 0);
  assert.equal(s.cacheDeleted, false);
});
