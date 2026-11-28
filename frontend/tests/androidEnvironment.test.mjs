import test from 'node:test';
import assert from 'node:assert/strict';
import { androidIdentityForHost, isExpectedAndroidReferrer } from '../src/utils/androidEnvironment.js';

const production = { packageName: 'ir.faipco.portal', scheme: 'faipco' };
const staging = { packageName: 'ir.faipco.portal.test', scheme: 'faipco-test' };

test('production retains its original package and native scheme', () => {
  assert.deepEqual(androidIdentityForHost('portal.faipco.ir'), production);
});

test('staging uses the test package and native scheme', () => {
  assert.deepEqual(androidIdentityForHost('portal-test.faipco.ir'), staging);
  assert.deepEqual(androidIdentityForHost('PORTAL-TEST.FAIPCO.IR.'), staging);
});

test('the staging hostname must match exactly', () => {
  assert.deepEqual(androidIdentityForHost('portal-test.faipco.ir.example.com'), production);
  assert.deepEqual(androidIdentityForHost('localhost'), production);
});

test('production and staging referrers are not interchangeable', () => {
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal', production.packageName), true);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.test/', staging.packageName), true);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.test', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal', staging.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://ir.faipco.portal.attacker', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('https://ir.faipco.portal', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('', production.packageName), false);
  assert.equal(isExpectedAndroidReferrer('android-app://user@ir.faipco.portal', production.packageName), false);
});

for (const [host, identity] of [['portal.faipco.ir', production], ['portal-test.faipco.ir', staging]]) {
  test(`native setup and portal links target the correct package for ${host}`, async () => {
    const savedWindow = globalThis.window;
    try {
      globalThis.window = { location: { hostname: host, host, origin: `https://${host}`, pathname: '/profile', search: '', href: `https://${host}/profile?q=1#section` } };
      const module = await import(`../src/utils/androidApp.js?environment=${host}`);
      module.openNativeSetup();
      assert.ok(window.location.href.includes(`;scheme=${identity.scheme};package=${identity.packageName};`));
      module.openNativePairing('test-code');
      assert.ok(window.location.href.includes(`;scheme=${identity.scheme};package=${identity.packageName};`));
      const current = window.location.href = `https://${host}/profile?q=1#section`;
      const href = module.portalAppHref();
      assert.ok(href.startsWith(`intent://setup#Intent;scheme=${identity.scheme};package=${identity.packageName};`));
      const fields = Object.fromEntries(href.split(';').slice(1, -1).map(field => field.split('=')));
      assert.equal(fields['B.onboarding'], 'true');
      assert.equal(fields['B.auto_request_notifications'], 'true');
      assert.equal(decodeURIComponent(fields['S.target_uri']), current);
      assert.equal(decodeURIComponent(fields['S.browser_fallback_url']), current);
      module.openPortalInApp('/notices?id=a%3Bb');
      assert.ok(window.location.href.includes(`S.target_uri=${encodeURIComponent('https://' + host + '/notices?id=a%3Bb')};`));
    } finally {
      if (savedWindow === undefined) delete globalThis.window;
      else globalThis.window = savedWindow;
    }
  });
}
