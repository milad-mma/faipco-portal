import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { runInNewContext } from 'node:vm';

const source = readFileSync(fileURLToPath(new URL('../src/utils/releaseSocket.js', import.meta.url)), 'utf8')
  .replace('import { onReleasePublished } from "./serviceWorker";', '')
  .replace('import.meta.env.VITE_API_BASE_URL', '"/api/v1"')
  .replace('export function connectReleaseNotifications', 'function connectReleaseNotifications')
  + '\n;globalThis.testAPI = { connectReleaseNotifications };';

function setup() {
  const received = [];
  const sockets = [];
  class WebSocketStub {
    static OPEN = 1;
    static CLOSED = 3;
    constructor(url, protocols) {
      this.url = url;
      this.protocols = protocols;
      this.readyState = 1;
      sockets.push(this);
    }
    close() { this.readyState = WebSocketStub.CLOSED; }
    message(data) { this.onmessage({ data: JSON.stringify(data) }); }
  }
  const window = new EventTarget();
  window.location = { origin: 'https://portal.example.test' };
  window.WebSocket = WebSocketStub;
  const document = new EventTarget();
  document.visibilityState = 'visible';
  const ctx = {
    window, document, WebSocket: WebSocketStub, URL,
    localStorage: { getItem(key) { return key === 'access_token' ? 'a.jwt.token' : null; } },
    onReleasePublished: (build) => received.push(build),
    setTimeout(fn, ms) { return { fn, ms }; }, clearTimeout() {},
  };
  runInNewContext(source, ctx);
  return { ...ctx.testAPI, received, sockets, window, document };
}

test('release socket requires session token, authenticates via subprotocol, not URL', () => {
  const s = setup();
  const stop = s.connectReleaseNotifications();
  assert.equal(s.sockets.length, 1);
  assert.equal(s.sockets[0].url, 'wss://portal.example.test/api/v1/system/release-ws');
  assert.equal(s.sockets[0].url.includes('token'), false);
  assert.deepEqual(Array.from(s.sockets[0].protocols), ['faipco-release', 'auth.a.jwt.token']);
  stop();
  assert.equal(s.sockets[0].readyState, 3);
});

test('release socket only forwards correct portal release messages', () => {
  const s = setup();
  const stop = s.connectReleaseNotifications();
  s.sockets[0].message({type: 'ping'});
  s.sockets[0].message({type: 'portal.release', build: '987654321'});
  s.sockets[0].message({type: 'attendance', build: 'bad'});
  assert.deepEqual(s.received, ['987654321']);
  stop();
});
