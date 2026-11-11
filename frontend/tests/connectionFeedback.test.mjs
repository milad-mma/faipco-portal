import test from 'node:test';
import assert from 'node:assert/strict';
import { connectionBannerKind, connectionBannerDelay } from '../src/utils/connectionFeedback.js';

test('a planned update never displays a misleading connectivity banner', () => {
  assert.equal(connectionBannerKind({ isOnline: false, isBrowserOffline: false, updating: true }), null);
  assert.equal(connectionBannerKind({ isOnline: false, isBrowserOffline: true, updating: true }), null);
});

test('server restart and real network outage have distinct classifications', () => {
  assert.equal(connectionBannerKind({ isOnline: false, isBrowserOffline: false, updating: false }), 'server');
  assert.equal(connectionBannerKind({ isOnline: false, isBrowserOffline: true, updating: false }), 'internet');
  assert.equal(connectionBannerKind({ isOnline: true, isBrowserOffline: false, updating: false }), null);
});

test('short connectivity interruptions are debounced before a banner appears', () => {
  assert.equal(connectionBannerDelay('server'), 6000);
  assert.equal(connectionBannerDelay('internet'), 2500);
});
