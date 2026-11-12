import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const cartable = readFileSync(new URL('../src/pages/OaCartablePage.jsx', import.meta.url), 'utf8');
const dashboard = readFileSync(new URL('../src/components/oa/DashboardLettersCard.jsx', import.meta.url), 'utf8');

test('returned-for-revision action links to its editable draft rather than letter preview', () => {
  assert.match(cartable, /it\.origin === "revision" \? `\/automation\/drafts\/\$\{it\.letter_id\}` : `\/automation\/letters\/\$\{it\.letter_id\}`/);
  assert.match(dashboard, /it\.origin === "revision" \? `\/automation\/drafts\/\$\{it\.letter_id\}` : `\/automation\/letters\/\$\{it\.letter_id\}`/);
});

test('cartable priority badge uses the same theme font as the rest of the portal', () => {
  assert.match(cartable, /function UrgencyBadge\(\{ urgency \}\)/);
  assert.match(cartable, /fontFamily: \(theme\) => theme\.typography\.fontFamily/);
  assert.match(cartable, /revision: "اصلاح نامه"/);
});
